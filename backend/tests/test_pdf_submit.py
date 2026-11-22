"""„Złóż wniosek” w kanale PDF: symulowane złożenie w ZUS (eZUS) albo w urzędzie, z odpowiedzią w poczcie."""

from test_applications import _complete_zam, _family, mail  # noqa: F401 - `mail` to fixtura

from app.mail.sim_inbox import PENDING
from app.services.applications import pdf_recipient


def test_pdf_recipient_follows_institution_from_catalog():
    assert pdf_recipient("ZAS-53") == "wnioski@zus.pl"
    assert pdf_recipient("ZAM") == "wnioski@zus.pl"  # „ZUS lub płatnik”
    assert pdf_recipient("SR-7") == "swiadczenia@um.krakow.pl"  # gmina (MOPS/OPS)
    assert pdf_recipient("URLOP-OJC") is None  # pracodawca: wnioski PDF do pracodawcy nie idą do urzędu


async def test_submitting_pdf_files_it_with_zus_and_schedules_a_reply(client, store, mail):  # noqa: F811
    h, ids = _family(client)
    app = _complete_zam(client, h, ids["Dziecko w drodze"], channel="pdf_download")
    assert client.post(f"/api/applications/{app['id']}/sign", headers=h).status_code == 200
    done = client.post(f"/api/applications/{app['id']}/submit", headers=h).json()
    assert done["status"] == "sent"
    assert done["recipient_email"] == "wnioski@zus.pl" and done["recipient_domain"] == "zus.pl"
    assert await store.get(PENDING, app["id"]) is not None  # odpowiedź ZUS przyjdzie do skrzynki
    assert mail.sent == []  # nie wysyłamy e-maila z poczty rodzica
