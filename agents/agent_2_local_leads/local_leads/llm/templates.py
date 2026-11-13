"""Deterministic template writer: the fallback when no LLM is configured or the LLM output is unusable.

Input is the same `facts` dict the LLM receives (writing.py). Outreach follows the sales playbook in
writing.py (personal hook from a measured fact -> business impact -> one clear offer with the local price ->
low-friction next step) and exists in English, Bulgarian and German (formal address). Other languages fall
back to English and the caller records it. Project briefs are internal and stay English.
"""
from __future__ import annotations

import re

OUTREACH_LANGS = ("en", "bg", "de")

APPROACH_TEXT = {
    "new_site": "a new mobile-first website",
    "relaunch": "relaunching the website on reliable hosting",
    "rebuild": "a modern rebuild of the website",
    "fixes": "a focused set of fixes",
}

# Why each problem costs the business customers - in their terms, not ours.
IMPACT = {
    "en": {
        "SOCIAL_MEDIA_ONLY": "There is only a social-media page, which Google barely shows and you don't control.",
        "FREE_SUBDOMAIN": "The site sits on a free subdomain, which looks less trustworthy than your own domain.",
        "PRICES_IN_BGN": "Prices are still only in leva, although prices in Bulgaria must be shown in euro now.",
        "MISSING_COMPANY_INFO": "I couldn't find the company details the law requires on a business website.",
        "NO_PRIVACY_POLICY": "I couldn't find a privacy or cookie policy, which the GDPR expects from every business site.",
        "WEBSITE_UNREACHABLE": "Anyone who clicks your link right now gets an error instead of your business.",
        "NO_HTTPS": "Browsers label the site 'Not secure', which makes visitors hesitate to call or send a form.",
        "NO_HTTPS_REDIRECT": "Visitors who type the address without https still land on the 'Not secure' version.",
        "SSL_EXPIRED": "Browsers show a full-screen security warning, so most visitors leave before they see you.",
        "SSL_INVALID_CERTIFICATE": "Browsers show a security warning, so most visitors leave before they see you.",
        "SSL_EXPIRING_SOON": "The security certificate runs out soon; after that browsers will warn visitors away.",
        "SLOW_PAGE_LOAD": "On a phone the page takes a while to open, and many people give up and pick the next "
                          "result.",
        "NOT_MOBILE_FRIENDLY": "On a phone visitors have to pinch and zoom, and most local searches happen on "
                               "phones.",
        "BROKEN_LINKS": "Some links lead to error pages, which makes the site look abandoned.",
        "OUTDATED_CMS": "The site software no longer gets security updates, which is how small sites get "
                        "hacked.",
        "OUTDATED_DESIGN": "The design looks dated, and people judge a business by its website in seconds.",
        "MIXED_CONTENT": "Parts of the page load insecurely, so browsers may show warnings or block images.",
        "NO_ONLINE_BOOKING": "Customers cannot book online, so those who search in the evening book elsewhere.",
        "NO_CONTACT_FORM": "There is no quick way to send an enquiry, so visitors who don't want to call just "
                           "leave.",
        "POOR_SEO": "Basic search settings are missing, so Google shows the site lower than it could.",
        "MISSING_META": "Google has no proper title and description to show, so the search result looks bare.",
        "ACCESSIBILITY_ISSUES": "Some visitors (older people, screen-reader users) struggle to use the site.",
        "NO_ANALYTICS": "There is no way to see how many people visit or where they come from.",
        "SECURITY_HEADERS_MISSING": "Standard browser protections are switched off, which leaves the site more "
                                    "exposed.",
    },
    "bg": {
        "SOCIAL_MEDIA_ONLY": "Имате само страница в социалните мрежи – Google почти не я показва и не е изцяло Ваша.",
        "FREE_SUBDOMAIN": "Сайтът е на безплатен поддомейн, което изглежда по-малко надеждно от собствен домейн.",
        "PRICES_IN_BGN": "Цените са все още само в лева, а от 8 август 2026 г. трябва да са в евро.",
        "MISSING_COMPANY_INFO": "Не открих фирмените данни (напр. ЕИК), които законът изисква на сайта.",
        "NO_PRIVACY_POLICY": "Не открих политика за поверителност и бисквитки, каквато GDPR изисква от всеки бизнес сайт.",
        "WEBSITE_UNREACHABLE": "В момента всеки, който отвори линка към сайта, вижда грешка вместо Вашия бизнес.",
        "NO_HTTPS": "Браузърите отбелязват сайта като „Не е защитен“ и посетителите се колебаят дали да се "
                    "обадят или да попълнят форма.",
        "NO_HTTPS_REDIRECT": "Който напише адреса без https, попада на версията, отбелязана като „Не е защитен“.",
        "SSL_EXPIRED": "Браузърите показват предупреждение за сигурност на цял екран и повечето посетители "
                       "напускат веднага.",
        "SSL_INVALID_CERTIFICATE": "Браузърите показват предупреждение за сигурност и повечето посетители "
                                   "напускат веднага.",
        "SSL_EXPIRING_SOON": "Сертификатът за сигурност изтича скоро; след това браузърите ще предупреждават "
                             "посетителите.",
        "SLOW_PAGE_LOAD": "На телефон страницата се отваря бавно и много хора се отказват и избират следващия "
                          "резултат.",
        "NOT_MOBILE_FRIENDLY": "На телефон сайтът трябва да се увеличава с пръсти, а повечето местни търсения "
                               "са именно от телефон.",
        "BROKEN_LINKS": "Някои връзки водят до страници с грешка и сайтът изглежда изоставен.",
        "OUTDATED_CMS": "Софтуерът на сайта вече не получава обновления за сигурност – така най-често се "
                        "хакват малките сайтове.",
        "OUTDATED_DESIGN": "Дизайнът изглежда остарял, а клиентите преценяват бизнеса по сайта за секунди.",
        "MIXED_CONTENT": "Части от страницата се зареждат незащитено и браузърите може да блокират снимки или да "
                         "показват предупреждения.",
        "NO_ONLINE_BOOKING": "Няма онлайн записване, така че клиентите, които търсят вечер, се записват другаде.",
        "NO_CONTACT_FORM": "Няма бърз начин за запитване и посетителите, които не искат да звънят, просто "
                           "напускат.",
        "POOR_SEO": "Липсват основни настройки за търсачките и Google показва сайта по-ниско, отколкото може.",
        "MISSING_META": "Google няма подходящо заглавие и описание за показване и резултатът изглежда беден.",
        "ACCESSIBILITY_ISSUES": "Част от посетителите (по-възрастни хора, незрящи) трудно използват сайта.",
        "NO_ANALYTICS": "Няма как да видите колко хора посещават сайта и откъде идват.",
        "SECURITY_HEADERS_MISSING": "Стандартните защити в браузъра са изключени и сайтът е по-уязвим.",
    },
    "de": {
        "SOCIAL_MEDIA_ONLY": "Es gibt nur eine Social-Media-Seite – Google zeigt sie kaum, und sie gehört Ihnen nicht.",
        "FREE_SUBDOMAIN": "Die Seite liegt auf einer kostenlosen Subdomain und wirkt weniger seriös als eine eigene.",
        "PRICES_IN_BGN": "Die Preise stehen noch in Lewa, obwohl in Bulgarien jetzt Euro-Preise Pflicht sind.",
        "MISSING_COMPANY_INFO": "Die gesetzlich vorgeschriebenen Firmenangaben habe ich auf der Website nicht gefunden.",
        "NO_PRIVACY_POLICY": "Eine Datenschutz- und Cookie-Erklärung, wie sie die DSGVO verlangt, habe ich nicht gefunden.",
        "WEBSITE_UNREACHABLE": "Wer gerade auf Ihren Link klickt, sieht eine Fehlermeldung statt Ihres Betriebs.",
        "NO_HTTPS": "Browser kennzeichnen die Seite als „Nicht sicher“ – viele Besucher zögern dann, anzurufen "
                    "oder ein Formular abzuschicken.",
        "NO_HTTPS_REDIRECT": "Wer die Adresse ohne https eintippt, landet weiterhin auf der „Nicht sicher“-Version.",
        "SSL_EXPIRED": "Browser zeigen eine ganzseitige Sicherheitswarnung, die meisten Besucher springen sofort ab.",
        "SSL_INVALID_CERTIFICATE": "Browser zeigen eine Sicherheitswarnung, die meisten Besucher springen sofort "
                                   "ab.",
        "SSL_EXPIRING_SOON": "Das Sicherheitszertifikat läuft bald ab; danach warnen Browser Ihre Besucher.",
        "SLOW_PAGE_LOAD": "Auf dem Handy lädt die Seite lange, viele brechen ab und wählen das nächste Ergebnis.",
        "NOT_MOBILE_FRIENDLY": "Auf dem Handy muss man zoomen – dabei laufen die meisten lokalen Suchen über das "
                               "Smartphone.",
        "BROKEN_LINKS": "Einige Links führen ins Leere, dadurch wirkt die Seite vernachlässigt.",
        "OUTDATED_CMS": "Die Software der Seite bekommt keine Sicherheitsupdates mehr – so werden kleine Seiten "
                        "am häufigsten gehackt.",
        "OUTDATED_DESIGN": "Das Design wirkt veraltet, und Kunden beurteilen einen Betrieb in Sekunden nach "
                           "seiner Website.",
        "MIXED_CONTENT": "Teile der Seite laden unverschlüsselt, Browser blockieren dann Bilder oder warnen.",
        "NO_ONLINE_BOOKING": "Es gibt keine Online-Buchung – wer abends sucht, bucht woanders.",
        "NO_CONTACT_FORM": "Es gibt keinen schnellen Weg für eine Anfrage; wer nicht anrufen möchte, geht.",
        "POOR_SEO": "Grundlegende Sucheinstellungen fehlen, deshalb zeigt Google die Seite weiter unten als nötig.",
        "MISSING_META": "Google fehlen Titel und Beschreibung, das Suchergebnis wirkt dadurch leer.",
        "ACCESSIBILITY_ISSUES": "Manche Besucher (Ältere, Screenreader-Nutzer) können die Seite nur schwer "
                                "nutzen.",
        "NO_ANALYTICS": "Sie können nicht sehen, wie viele Besucher kommen und woher.",
        "SECURITY_HEADERS_MISSING": "Standard-Schutzfunktionen des Browsers sind nicht aktiv, die Seite ist "
                                    "angreifbarer.",
    },
}

SUBJECTS = {
    "en": {"new_site": "{name}: customers who look you up online", "fixes": "{domain}: a few quick wins",
           "relaunch": "{domain} is not loading at the moment", "rebuild": "An idea for the {name} website"},
    "bg": {"new_site": "{name}: клиентите, които Ви търсят онлайн", "fixes": "{domain}: няколко бързи подобрения",
           "relaunch": "{domain} не се зарежда в момента", "rebuild": "Идея за сайта на {name}"},
    "de": {"new_site": "{name}: Kunden, die Sie online suchen", "fixes": "{domain}: ein paar schnelle Verbesserungen",
           "relaunch": "{domain} ist gerade nicht erreichbar", "rebuild": "Eine Idee für die Website von {name}"},
}


def money(estimate: dict, lang: str = "en") -> str:
    b = estimate["budget"]
    lo, hi, cur = b["min"], b["max"], b["currency"]
    if lang == "bg":  # ЗЕТ чл. 4, ал. 2: say whether taxes are included
        return f"{lo:,.0f} – {hi:,.0f} {cur} без ДДС".replace(",", " ")
    if lang == "de":
        return f"{lo:,.0f}–{hi:,.0f} {cur}".replace(",", ".")
    return f"{cur} {lo:,.0f}-{hi:,.0f}"


def _first_sentence(text: str, limit: int = 220) -> str:
    s = (text or "").split(". ")[0].strip().rstrip(".")
    return (s[: limit - 1] + "…") if len(s) > limit else s


def brief_text(facts: dict) -> dict:
    b, est, problems = facts["business"], facts["estimate"], facts["problems"]
    name, approach = b["name"], est["approach"]
    title = {"new_site": f"New website for {name}", "relaunch": f"Website relaunch for {name}",
             "rebuild": f"Website rebuild for {name}"}.get(approach, f"Website improvements for {name}")
    where = ", ".join(p for p in (b.get("category"), b.get("city")) if p)
    if approach == "new_site":
        finding = "No website was found in the business listing."
    else:
        finding = (f"An automated scan of {b.get('website')} found {len(problems)} issue(s): "
                   + "; ".join(p["title"] for p in problems[:6]) + ".")
    summary = (f"{name}{f' ({where})' if where else ''}. {finding} Proposed: {APPROACH_TEXT[approach]}. "
               f"Estimated effort {est['hours']['min']}-{est['hours']['max']} hours, budget {money(est)} "
               f"(local market rate).")
    impacts = [IMPACT["en"].get(p["code"]) for p in problems[:4]]
    pitch = "\n".join(f"- {i}" for i in impacts if i)
    solution = (f"Deliver {APPROACH_TEXT[approach]} that resolves the issues found:\n"
                + "\n".join(f"- {item}" for item in est["scope_items"])
                + f"\n\nSuggested stack: {', '.join(est['tech_stack']) or 'to be agreed with the client'}."
                + (f"\n\nWhy it matters to the client (lead with this in the call):\n{pitch}" if pitch else "")
                + "".join(f"\n- {n}" for n in facts.get("sales_notes", [])))
    top = ", ".join(p["code"] for p in problems[:4]) or "none"
    approval = (f"Score {facts.get('score')}/100. Top issues: {top}. Estimate {est['hours']['min']}-"
                f"{est['hours']['max']} h / {money(est)}.")
    return {"title": title[:120], "summary": summary, "proposed_solution": solution, "approval_summary": approval}


def outreach_language(lang: str) -> str:
    code = (lang or "en").split("-")[0].lower()
    return code if code in OUTREACH_LANGS else "en"


def outreach_text(facts: dict) -> dict:
    lang = outreach_language(facts.get("language", "en"))
    b, est, problems = facts["business"], facts["estimate"], facts["problems"]
    name, approach = b["name"], est["approach"]
    domain = b.get("domain") or b.get("website") or name
    city = b.get("city") or ""
    if lang == "bg" and not re.search("[а-яА-Я]", city):
        city = ""  # a Latin "Plovdiv" inside Bulgarian text reads wrong
    city = city or {"en": "your area", "bg": "района", "de": "Ihrer Region"}[lang]
    h = f"{est['hours']['min']}{'-' if lang == 'en' else '–'}{est['hours']['max']}"
    price = money(est, lang)
    subject = SUBJECTS[lang]["fixes" if approach not in SUBJECTS[lang] else approach].format(name=name, domain=domain)
    impact = IMPACT[lang]
    if lang == "en":
        points = "\n".join(f"- {_first_sentence(p['description'])}. {impact.get(p['code'], '')}".rstrip()
                           for p in problems[:3])
    else:
        points = "\n".join(f"- {impact.get(p['code']) or p['title']}" for p in problems[:3])
    social = next((p for p in problems if p["code"] == "SOCIAL_MEDIA_ONLY"), None)
    template = _BODIES[lang]["new_site" if approach == "new_site" else "improve"]
    if social:
        template = template.replace(*_SOCIAL_SWAP[lang])
    body = template.format(
        name=name, city=city, domain=domain, points=points, price=price, hours=h,
        work=_WORK[lang][approach])
    return {"subject": subject[:120], "body": body}


_WORK = {
    "en": {"new_site": "", "relaunch": "getting the site back online on reliable hosting",
           "rebuild": "a modern, mobile-friendly rebuild that keeps your content",
           "fixes": "fixing exactly these points, without a new website"},
    "bg": {"new_site": "", "relaunch": "връщане на сайта онлайн на надежден хостинг",
           "rebuild": "модерен сайт, удобен за телефон, като запазим съдържанието Ви",
           "fixes": "поправка точно на тези неща, без нов сайт"},
    "de": {"new_site": "", "relaunch": "die Seite auf zuverlässigem Hosting wieder online zu bringen",
           "rebuild": "einen modernen, handyfreundlichen Neuaufbau, der Ihre Inhalte übernimmt",
           "fixes": "genau diese Punkte zu beheben – ohne neue Website"},
}

_BODIES = {
    "en": {
        "new_site": (
            "Hello {name} team,\n\n"
            "I was looking at local businesses in {city} and found {name} on the map, but no website linked to it.\n\n"
            "Most customers check their phone first: opening hours, services, prices and how to reach you. When "
            "there is no site, many of them simply pick the next business that has one.\n\n"
            "I build fast, simple websites for local businesses: mobile-first, with your services, opening hours, "
            "a map, a call button and a contact form, on your own domain. For a business like yours that is "
            "typically {price} ({hours} hours of work).\n\n"
            "Shall I send you a short proposal with two or three example layouts for your homepage?"),
        "improve": (
            "Hello {name} team,\n\n"
            "I had a look at {domain} while researching local businesses in {city}. A few things are quietly "
            "costing you enquiries:\n\n{points}\n\n"
            "My suggestion is {work}. That is about {hours} hours of work, estimated {price}.\n\n"
            "Would a short proposal with the details be useful? I'm also happy to walk you through it in a "
            "10-minute call."),
    },
    "bg": {
        "new_site": (
            "Здравейте, екип на {name},\n\n"
            "Разглеждах местните бизнеси в {city} и открих {name} на картата, но без уебсайт към профила.\n\n"
            "Повечето клиенти първо проверяват в телефона си – работно време, услуги, цени и как да се свържат с "
            "Вас. Когато няма сайт, много от тях просто избират следващия бизнес, който има.\n\n"
            "Изработвам бързи и ясни сайтове за местни бизнеси: удобни за телефон, с Вашите услуги, работно време, "
            "карта, бутон за обаждане и форма за контакт, на собствен домейн. За бизнес като Вашия това обикновено "
            "е {price} ({hours} часа работа).\n\n"
            "Да Ви изпратя ли кратко предложение с два-три примерни варианта на началната страница?"),
        "improve": (
            "Здравейте, екип на {name},\n\n"
            "Разгледах {domain}, докато проучвах местните бизнеси в {city}. Няколко неща тихомълком Ви струват "
            "запитвания:\n\n{points}\n\n"
            "Предлагам {work}. Това са около {hours} часа работа, на прогнозна цена {price}.\n\n"
            "Да Ви изпратя ли кратко предложение с подробностите? Мога да Ви го представя и в 10-минутен разговор."),
    },
    "de": {
        "new_site": (
            "Guten Tag, liebes Team von {name},\n\n"
            "bei der Recherche zu lokalen Betrieben in {city} bin ich auf {name} gestoßen – allerdings ohne "
            "verlinkte Website.\n\n"
            "Die meisten Kunden schauen zuerst auf dem Handy nach: Öffnungszeiten, Leistungen, Preise und wie man "
            "Sie erreicht. Ohne Website landen viele beim nächsten Betrieb, der eine hat.\n\n"
            "Ich erstelle schnelle, übersichtliche Websites für lokale Unternehmen: für Smartphones optimiert, mit "
            "Ihren Leistungen, Öffnungszeiten, Karte, Anruf-Button und Kontaktformular – auf Ihrer eigenen Domain. "
            "Für einen Betrieb wie Ihren liegt das in der Regel bei {price} ({hours} Stunden Aufwand).\n\n"
            "Darf ich Ihnen ein kurzes Angebot mit zwei, drei Entwürfen für Ihre Startseite schicken?"),
        "improve": (
            "Guten Tag, liebes Team von {name},\n\n"
            "bei der Recherche zu lokalen Betrieben in {city} habe ich mir {domain} angesehen. Ein paar Punkte "
            "kosten Sie still und leise Anfragen:\n\n{points}\n\n"
            "Mein Vorschlag: {work}. Das sind etwa {hours} Stunden Aufwand, geschätzt {price}.\n\n"
            "Soll ich Ihnen ein kurzes Angebot mit den Details schicken? Gern erkläre ich es auch in einem "
            "10-minütigen Telefonat."),
    },
}

# Facebook-only businesses: same e-mail, different observation.
_SOCIAL_SWAP = {
    "en": ("found {name} on the map, but no website linked to it.",
           "found {name}, but only a social-media page instead of a website."),
    "bg": ("открих {name} на картата, но без уебсайт към профила.",
           "открих {name}, но само със страница в социалните мрежи вместо сайт."),
    "de": ("bin ich auf {name} gestoßen – allerdings ohne verlinkte Website.",
           "bin ich auf {name} gestoßen – allerdings nur mit einer Social-Media-Seite statt einer Website."),
}
