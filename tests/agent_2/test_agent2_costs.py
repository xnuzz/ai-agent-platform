"""Cost controls: LLM response cache, per-task LLM call budget, token accounting, cross-task scan reuse."""
from local_leads import LocalLeadsAgent
from local_leads.discovery.fake import FakeDiscoveryProvider
from local_leads.llm.fake import FakeLLMProvider
from local_leads.writing import Writer
from test_agent2_handler import businesses, settings
from test_agent2_llm import FACTS

from a2_helpers import FakeContext, good_site_routes, poor_site_routes


class CountingLLM(FakeLLMProvider):
    def __init__(self):
        super().__init__()
        self.n = 0
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    def usage_snapshot(self):
        return dict(self.usage)

    def generate_json(self, **kw):
        self.n += 1
        self.usage["input_tokens"] += 100
        self.usage["output_tokens"] += 40
        return super().generate_json(**kw)


def test_identical_requests_hit_the_cache_and_tokens_are_counted():
    llm = CountingLLM()
    w = Writer(llm)
    first, second = w.brief(FACTS), w.brief(FACTS)
    assert first.data == second.data and llm.n == 1
    assert w.task_stats() == {"llm_calls": 1, "cache_hits": 1, "template_fallbacks": 0, "budget_exhausted": 0,
                              "input_tokens": 100, "output_tokens": 40}
    w.start_task()                                     # per-task counters reset, cache kept
    w.brief(FACTS)
    assert llm.n == 1 and w.task_stats()["cache_hits"] == 1 and w.task_stats()["input_tokens"] == 0


def test_call_budget_falls_back_to_templates_and_says_so():
    llm = CountingLLM()
    w = Writer(llm, max_calls=1)
    w.brief(FACTS)
    over = w.outreach(FACTS)
    assert llm.n == 1 and over.author == "template" and "budget" in over.note
    assert w.task_stats()["budget_exhausted"] == 1 and w.task_stats()["template_fallbacks"] == 1


def test_second_task_reuses_website_scans(sites):
    poor = sites(poor_site_routes(), host="127.0.0.2")
    good = sites(good_site_routes(), host="127.0.0.3")
    supp = sites(poor_site_routes(), host="127.0.0.11")
    agent = LocalLeadsAgent(settings(), discovery=FakeDiscoveryProvider(businesses(poor, good, supp)),
                            llm=CountingLLM())
    task = {"location": {"city": "Plovdiv", "country_code": "BG"}}
    first = agent(FakeContext(task))
    hits_on_poor = len(poor.requests)
    second = agent(FakeContext(task))
    agent.close()
    assert first["scan_cache_hits"] == 0 and second["scan_cache_hits"] >= 2
    assert len(poor.requests) == hits_on_poor          # the site was not crawled again
    assert second["llm_usage"]["llm_calls"] == 0 and second["llm_usage"]["cache_hits"] > 0
