import os.path
import urllib
from contextlib import contextmanager
from mimetypes import guess_type

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.dispatch import Signal
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from taggit.managers import TaggableManager

from wagtail.models import CollectionMember, ReferenceIndex
from wagtail.search import index
from wagtail.search.queryset import SearchableQuerySetMixin
from wagtail.utils.file import hash_filelike


class DocumentQuerySet(SearchableQuerySetMixin, models.QuerySet):
    pass


class AbstractDocument(CollectionMember, index.Indexed, models.Model):
    title = models.CharField(max_length=255, verbose_name=_("title"))
    file = models.FileField(upload_to="documents", verbose_name=_("file"))
    created_at = models.DateTimeField(verbose_name=_("created at"), auto_now_add=True)
    uploaded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("uploaded by user"),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
    )
    uploaded_by_user.wagtail_reference_index_ignore = True

    tags = TaggableManager(help_text=None, blank=True, verbose_name=_("tags"))

    file_size = models.PositiveBigIntegerField(null=True, editable=False)
    # A SHA-1 hash of the file contents
    file_hash = models.CharField(max_length=40, blank=True, editable=False)

    objects = DocumentQuerySet.as_manager()

    search_fields = CollectionMember.search_fields + [
        index.SearchField("title", boost=10),
        index.AutocompleteField("title"),
        index.FilterField("id"),
        index.FilterField("title"),
        index.RelatedFields(
            "tags",
            [
                index.SearchField("name", boost=10),
                index.AutocompleteField("name"),
            ],
        ),
        index.FilterField("uploaded_by_user"),
        index.FilterField("created_at"),
    ]

    def clean(self):
        """
        Checks for WAGTAILDOCS_EXTENSIONS and validates the uploaded file
        based on allowed extensions that were specified.
        Warning : This doesn't always ensure that the uploaded file is valid
        as files can be renamed to have an extension no matter what
        data they contain.

        More info : https://docs.djangoproject.com/en/3.1/ref/validators/#fileextensionvalidator
        """
        allowed_extensions = getattr(settings, "WAGTAILDOCS_EXTENSIONS", None)
        if allowed_extensions:
            validate = FileExtensionValidator(allowed_extensions)
            try:
                validate(self.file)
            except ValidationError as e:
                raise ValidationError({"file": e.messages[0]})

    def is_stored_locally(self):
        """
        Returns True if the image is hosted on the local filesystem
        """
        try:
            self.file.path

            return True
        except NotImplementedError:
            return False

    @contextmanager
    def open_file(self):
        # Open file if it is closed
        close_file = False
        f = self.file

        if f.closed:
            # Reopen the file
            if self.is_stored_locally():
                f.open("rb")
            else:
                # Some external storage backends don't allow reopening
                # the file. Get a fresh file instance. #1397
                storage = self._meta.get_field("file").storage
                f = storage.open(f.name, "rb")

            close_file = True

        # Seek to beginning
        f.seek(0)

        try:
            yield f
        finally:
            if close_file:
                f.close()

    def get_file_size(self):
        if self.file_size is None:
            try:
                self.file_size = self.file.size
            except Exception:  # noqa: BLE001
                # File doesn't exist
                return

            self.save(update_fields=["file_size"])

        return self.file_size

    def _set_file_hash(self):
        with self.open_file() as f:
            self.file_hash = hash_filelike(f)

    def get_file_hash(self):
        if self.file_hash == "":
            self._set_file_hash()
            self.save(update_fields=["file_hash"])

        return self.file_hash

    def _set_document_file_metadata(self):
        self.file.open()

        # Set new document file size
        self.file_size = self.file.size

        # Set new document file hash
        self._set_file_hash()
        self.file.seek(0)

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def file_extension(self):
        return os.path.splitext(self.filename)[1][1:]

    @property
    def url(self):
        if getattr(settings, "WAGTAILDOCS_SERVE_METHOD", None) == "direct":
            try:
                return self.file.url
            except NotImplementedError:
                # backend does not provide a url, so fall back on the serve view
                pass

        return reverse("wagtaildocs_serve", args=[self.id, self.filename])

    def get_usage(self):
        return ReferenceIndex.get_grouped_references_to(self)

    @property
    def usage_url(self):
        return reverse("wagtaildocs:document_usage", args=(self.id,))

    def is_editable_by_user(self, user):
        from wagtail.documents.permissions import permission_policy

        return permission_policy.user_has_permission_for_instance(user, "change", self)

    @property
    def content_type(self):
        content_types_lookup = getattr(settings, "WAGTAILDOCS_CONTENT_TYPES", {})
        return (
            content_types_lookup.get(self.file_extension.lower())
            or guess_type(self.filename)[0]
            or "application/octet-stream"
        )

    @property
    def content_disposition(self):
        inline_content_types = getattr(
            settings, "WAGTAILDOCS_INLINE_CONTENT_TYPES", ["application/pdf"]
        )
        if self.content_type in inline_content_types:
            return "inline"
        else:
            return "attachment; filename={0}; filename*=UTF-8''{0}".format(
                urllib.parse.quote(self.filename)
            )

    class Meta:
        abstract = True
        verbose_name = _("document")
        verbose_name_plural = _("documents")


class Document(AbstractDocument):
    admin_form_fields = ("title", "file", "collection", "tags")

    class Meta(AbstractDocument.Meta):
        permissions = [
            ("choose_document", "Can choose document"),
        ]


# provides args: request
document_served = Signal()
