from celery import shared_task


@shared_task(name="orchestration.reap_expired_leases")
def reap_expired_leases_task() -> int:
    from .services import reap_expired_leases

    return reap_expired_leases()
