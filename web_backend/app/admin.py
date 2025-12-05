from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import User, AccessToken, Image, ExtractedText


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active', 'date_joined', 'image_count')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login')
    ordering = ('-date_joined',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('username', 'email', 'first_name', 'last_name')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Images'


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'created_at', 'last_used_at', 'expires_at')
    list_filter = ('revoked', 'created_at', 'expires_at')
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at', 'last_used_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Token Info', {
            'fields': ('user', 'name')
        }),
        ('Status', {
            'fields': ('revoked', 'last_used_at', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('scopes', 'ip_whitelist', 'metadata', 'created_at')
        }),
    )
    
    def is_active(self, obj):
        return not obj.revoked and (not obj.expires_at or obj.expires_at > timezone.now())
    is_active.boolean = True
    is_active.short_description = 'Active'


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('filename', 'user', 'ocr_status_badge', 'size_display', 'uploaded_at', 'has_texts')
    list_filter = ('ocr_status', 'storage_provider', 'uploaded_at', 'content_type')
    search_fields = ('filename', 'user__username', 'sha256_hash', 'storage_key')
    readonly_fields = ('sha256_hash', 'uploaded_at', 'ocr_started_at', 'ocr_completed_at', 'deduplicated_to')
    ordering = ('-uploaded_at',)
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('File Info', {
            'fields': ('user', 'filename', 'content_type', 'size_bytes', 'sha256_hash')
        }),
        ('Storage', {
            'fields': ('storage_provider', 'storage_key', 'deduplicated_to')
        }),
        ('OCR Status', {
            'fields': ('ocr_status', 'ocr_started_at', 'ocr_completed_at', 'model_version')
        }),
        ('Metadata', {
            'fields': ('ollama_response', 'additional_meta', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def ocr_status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'processing': 'blue',
            'done': 'green',
            'failed': 'red',
            'cached': 'orange'
        }
        color = colors.get(obj.ocr_status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.ocr_status.upper()
        )
    ocr_status_badge.short_description = 'OCR Status'
    
    def size_display(self, obj):
        if obj.size_bytes:
            if obj.size_bytes < 1024:
                return f"{obj.size_bytes} B"
            elif obj.size_bytes < 1024 * 1024:
                return f"{obj.size_bytes / 1024:.1f} KB"
            else:
                return f"{obj.size_bytes / (1024 * 1024):.1f} MB"
        return "—"
    size_display.short_description = 'Size'
    
    def has_texts(self, obj):
        return obj.texts.count() > 0
    has_texts.boolean = True
    has_texts.short_description = 'Has Text'


@admin.register(ExtractedText)
class ExtractedTextAdmin(admin.ModelAdmin):
    list_display = ('id', 'image_link', 'user', 'pages', 'language', 'confidence_display', 'is_cached', 'created_at')
    list_filter = ('is_cached', 'language', 'source', 'created_at')
    search_fields = ('image__filename', 'user__username', 'extracted_text')
    readonly_fields = ('created_at', 'tokens_count')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('image', 'user', 'source', 'is_cached')
        }),
        ('Extracted Content', {
            'fields': ('extracted_text', 'structured')
        }),
        ('Metadata', {
            'fields': ('pages', 'language', 'confidence', 'tokens_count', 'model_version', 'created_at')
        }),
    )
    
    def image_link(self, obj):
        if obj.image:
            return format_html(
                '<a href="/admin/app/image/{}/change/">{}</a>',
                obj.image.id, obj.image.filename
            )
        return "—"
    image_link.short_description = 'Image'
    
    def confidence_display(self, obj):
        if obj.confidence:
            return f"{obj.confidence:.1%}"
        return "—"
    confidence_display.short_description = 'Confidence'


# RateLimit admin removed because the model is being deleted.