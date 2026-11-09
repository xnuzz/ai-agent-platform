from celery import shared_task


@shared_task(name="privacy.purge_stale_contacts")
def purge_stale_contacts_task() -> int:
    from .services import purge_stale_contacts

    return purge_stale_contacts()
