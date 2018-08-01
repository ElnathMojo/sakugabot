from django.contrib.admin import AdminSite


class MyAdminSite(AdminSite):
    site_header = 'Monty Python administration'


admin_site = MyAdminSite(name='admin')
