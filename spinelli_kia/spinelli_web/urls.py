from django.urls import path

from portal import customer, manager, misc, staff

urlpatterns = [
    # customer portal
    path("", customer.home),
    path("vehicles/", customer.vehicle_list),
    path("vehicles/<str:stock>/", customer.vehicle_detail),
    path("test-drive/", customer.test_drive_form),
    path("test-drive/received/<str:tid>/", customer.test_drive_received),
    path("signin/", customer.signin),
    path("signout/", customer.signout),
    path("account/", customer.account),
    path("track/", customer.track),
    path("messages/", customer.messages_list),
    path("messages/new/", customer.message_new),
    path("messages/<str:cid>/", customer.conversation),
    path("contact/", customer.contact),
    # receptionist
    path("staff/signin/", staff.staff_signin),
    path("staff/signout/", staff.staff_signout),
    path("staff/requests/", staff.requests_list),
    path("staff/requests/<str:tid>/", staff.request_review),
    path("staff/requests/<str:tid>/deny/", staff.request_deny),
    path("staff/customers/", staff.customers),
    path("staff/customers/new/", staff.customer_new),
    path("staff/customers/<str:cid>/", staff.customer_profile),
    path("staff/customers/<str:cid>/edit/", staff.customer_edit),
    path("staff/schedule/", staff.schedule),
    path("staff/messages/", staff.staff_messages),
    path("staff/messages/<str:cid>/", staff.staff_conversation),
    path("staff/service/<str:rid>/", staff.service_request),
    # sales manager
    path("manager/customers/", manager.my_customers),
    path("manager/customers/<str:cid>/", manager.manager_customer),
    path("manager/schedule/", manager.manager_schedule),
    path("manager/messages/", manager.manager_messages),
    path("manager/messages/<str:cid>/", manager.manager_conversation),
    path("manager/reports/", manager.manager_reports),
    # admin
    path("admin-portal/rules/", manager.rules),
    path("admin-portal/reports/", manager.admin_reports),
    # language and demo tools
    path("lang/<str:code>/", misc.set_lang),
    path("demo/", misc.demo),
]
