from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SubscriptionPlan, Subscription, OTP, CreditPlan, Payment, CreditTransaction


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'profile_picture', 'is_pro', 'is_verified', 'credits_balance')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'full_name', 'credits_balance', 'is_pro', 'is_verified', 'is_staff')
    search_fields = ('email', 'full_name')
    ordering = ('email',)


admin.site.register(SubscriptionPlan)
admin.site.register(Subscription)
admin.site.register(OTP)
admin.site.register(CreditPlan)
admin.site.register(Payment)
admin.site.register(CreditTransaction)
