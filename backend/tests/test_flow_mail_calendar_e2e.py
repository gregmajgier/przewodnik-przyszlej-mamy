"""E2E planu 09: Anna składa wniosek -> symulowane odpowiedzi -> zmiana statusu -> wpis w kalendarzu i powiadomienia.

Wniosek składany prawdziwym kreatorem planu 08 (`send_application`).
"""

from datetime import date, timedelta

from conftest import login, send_application


def test_anna_application_reply_status_calendar_notification(client):
    anna = login(client, "persona-nowak-anna")
    code = client.post("/api/families", headers=anna).json()["family"]["invite_code"]
    piotr = login(client, "persona-nowak-piotr")
    req = client.post("/api/families/join", json={"code": code}, headers=piotr).json()
    client.post(f"/api/families/me/join-requests/{req['id']}/accept", headers=anna)
    due = (date.today() + timedelta(days=60)).isoformat()
    client.post("/api/families/me/children", json={"name": "Maluszek", "due_date": due}, headers=anna)

    # 1. Anna wysyła wniosek o urlop do pracodawcy
    app = send_application(client, anna)
    assert app["status"] == "sent" and app["thread_id"]

    # 2. kalendarz od razu pokazuje wniosek z „kto złożył”
    cal = client.get("/api/calendar", headers=piotr).json()
    [entry] = [e for e in cal if e["source_ref"] == f"application:{app['id']}"]
    assert entry["actor_name"] == "Anna Nowak" and entry["status"] == "sent"

    # 3. odpowiedzi pracodawcy (symulacja) -> klasyfikacja (DemoLLM) -> status
    r = client.post("/api/mail/simulate-replies", headers=anna).json()
    assert r["status_changes"] == 2
    [thread] = client.get("/api/mail/threads", headers=piotr).json()
    assert thread["application"]["status"] == "accepted"

    # 4. kalendarz i powiadomienia obojga rodziców
    cal = client.get("/api/calendar", headers=anna).json()
    [entry] = [e for e in cal if e["source_ref"] == f"application:{app['id']}"]
    assert entry["status"] == "accepted" and "zaakceptowany" in entry["summary"]
    for h in (anna, piotr):
        texts = [n["text"] for n in client.get("/api/notifications", headers=h).json()]
        assert any("URLOP-MAC-ROD" in t and "decyzja pozytywna" in t for t in texts)

    # 5. ponowna synchronizacja nic nie dubluje
    assert client.post("/api/mail/sync", headers=anna).json()["status_changes"] == 0
    assert len(client.get("/api/notifications", headers=anna).json()) == 2
    # maile niezwiązane z wnioskami nie trafiły do wątków
    assert all(m["from_addr"] != "babcia.krysia@gmail.com" for m in thread["messages"])
