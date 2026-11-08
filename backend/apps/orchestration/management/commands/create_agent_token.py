from django.core.management.base import BaseCommand, CommandError

from apps.common.enums import AgentType
from apps.orchestration.models import AgentToken


class Command(BaseCommand):
    help = "Issue an agent service token. The key is printed ONCE; store it in the agent's secret store."

    def add_arguments(self, parser):
        parser.add_argument("--agent", required=True, choices=AgentType.values)
        parser.add_argument("--name", required=True)

    def handle(self, *args, agent, name, **opts):
        if not name.strip():
            raise CommandError("--name must not be empty")
        token, key = AgentToken.issue(name=name, agent=agent)
        self.stdout.write(f"token_id={token.id}\nagent={agent}\nPLATFORM_AGENT_TOKEN={key}")
