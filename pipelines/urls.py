from django.urls import path

from . import views

urlpatterns = [
    path("", views.index_page, name="index"),
    path("runs/<int:run_id>/", views.run_page, name="run"),
    path("api/pipelines/", views.pipelines_api),
    path("api/pipelines/<int:pipeline_id>/", views.pipeline_detail_api),
    path("api/pipelines/<int:pipeline_id>/run/", views.trigger_run_api),
    path("api/runs/<int:run_id>/", views.run_detail_api),
]
