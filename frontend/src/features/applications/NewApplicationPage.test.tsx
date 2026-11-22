import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import type { FamilyView } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import NewApplicationPage from './NewApplicationPage'
import { FORMS, makeApp, makeFamily } from './testData'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

function Tree() {
  return (
    <Routes>
      <Route path="/wnioski/nowy" element={<NewApplicationPage />} />
      <Route path="/wnioski/:id" element={<p>Kreator wniosku</p>} />
      <Route path="/start" element={<p>Start</p>} />
      <Route path="/rodzina" element={<p>Rodzina</p>} />
    </Routes>
  )
}

function renderPage(route = '/wnioski/nowy', family: FamilyView | null = makeFamily(ANNA)) {
  return renderWithSession(<Tree />, { route, session: makeSession({ family }) })
}

beforeEach(() => vi.clearAllMocks())

describe('NewApplicationPage', () => {
  it('pokazuje wnioski jako karty wyboru, polecane na górze i oznaczone', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage()
    const radios = await screen.findAllByRole('radio')
    expect(radios[0]).toHaveAccessibleName(/urlop macierzyński i rodzicielski.*polecany/i)
    expect(radios[1]).toHaveAccessibleName(/zasiłek macierzyński.*polecany/i)
    expect(screen.getByRole('radio', { name: /800\+/ })).not.toHaveAccessibleName(/polecany/i)
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeDisabled()
  })

  it('kod z adresu (?form=) wybiera wniosek; dziecko jest wymagane, bez dzieci w sytuacji straty', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=ZAM')
    expect(await screen.findByRole('radio', { name: /zasiłek macierzyński/i })).toHaveAttribute('aria-checked', 'true')
    const kids = within(screen.getByRole('radiogroup', { name: /którego dziecka dotyczy/i }))
    expect(kids.getByRole('radio', { name: /Maja/ })).toBeInTheDocument()
    expect(kids.getByRole('radio', { name: /Maleństwo.*termin 20\.01\.2027/ })).toBeInTheDocument()
    expect(kids.queryByRole('radio', { name: /Utracone/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeDisabled()
    await userEvent.click(kids.getByRole('radio', { name: /Maleństwo/ }))
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeEnabled()
  })

  it('wybrany wniosek zwija listę do jednej karty; „Zmień wniosek” ją rozwija, a kolejny wybór znów zwija', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=ZAM')
    const picker = () => within(screen.getByRole('radiogroup', { name: /rodzaj wniosku/i }))
    await screen.findByRole('radiogroup', { name: /którego dziecka dotyczy/i })
    expect(picker().getAllByRole('radio')).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: /zmień wniosek/i }))
    expect(picker().getAllByRole('radio').length).toBeGreaterThan(1)
    expect(screen.queryByRole('radiogroup', { name: /którego dziecka dotyczy/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeDisabled()

    await userEvent.click(picker().getByRole('radio', { name: /zasiłek chorobowy/i }))
    expect(picker().getAllByRole('radio')).toHaveLength(1)
    expect(picker().getByRole('radio')).toHaveAccessibleName(/zasiłek chorobowy/i)
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeEnabled()
  })

  it('zakłada wniosek z dzieckiem i wybranym kanałem, potem przechodzi do kreatora', async () => {
    const mocked = routeApi({
      'GET /api/applications/forms': FORMS,
      'POST /api/applications': makeApp({ id: 'app-77', form_code: 'ZAM', channel: 'pdf_download' }),
    })
    renderPage('/wnioski/nowy?form=ZAM')
    await userEvent.click(await screen.findByRole('radio', { name: /Maleństwo/ }))
    expect(screen.getByRole('radio', { name: /formularz online/i })).toHaveAttribute('aria-checked', 'true') // kanał domyślny
    await userEvent.click(screen.getByRole('radio', { name: /pdf do pobrania/i }))
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications', {
        method: 'POST',
        body: { form_code: 'ZAM', child_id: 'c-drodze', channel: 'pdf_download' },
      }),
    )
    expect(await screen.findByText('Kreator wniosku')).toBeInTheDocument()
  })

  it('jedno dziecko jest wybierane automatycznie, a pojedynczy kanał nie jest wysyłany', async () => {
    const family = makeFamily(ANNA)
    family.children = [family.children[0]]
    const mocked = routeApi({ 'GET /api/applications/forms': FORMS, 'POST /api/applications': makeApp({ id: 'app-2' }) })
    renderPage('/wnioski/nowy?form=800PLUS', family)
    expect(await screen.findByText(/składa się tylko elektronicznie/i)).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: /jak złożyć wniosek/i })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications', { method: 'POST', body: { form_code: '800PLUS', child_id: 'c-maja' } }),
    )
  })

  it('wniosek przypisany do dziecka (?child=) nie pokazuje innych dzieci do wyboru i zakłada się od razu', async () => {
    const mocked = routeApi({ 'GET /api/applications/forms': FORMS, 'POST /api/applications': makeApp({ id: 'app-4' }) })
    renderPage('/wnioski/nowy?form=ZAM&child=c-drodze')
    await screen.findByRole('radio', { name: /zasiłek macierzyński/i })
    expect(screen.queryByRole('radiogroup', { name: /którego dziecka dotyczy/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: /Maja/ })).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: /wniosek dotyczy/i })).toHaveTextContent(/Maleństwo/)
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications', expect.objectContaining({ method: 'POST', body: expect.objectContaining({ child_id: 'c-drodze' }) })),
    )
  })

  it('nieznane ?child= nie blokuje użytkownika — wraca zwykły wybór dziecka', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=ZAM&child=nie-ma-takiego')
    const kids = within(await screen.findByRole('radiogroup', { name: /którego dziecka dotyczy/i }))
    expect(kids.getAllByRole('radio').length).toBeGreaterThan(1)
  })

  it('wniosek bez dziecka (np. zasiłek chorobowy) nie pyta o dziecko', async () => {
    const mocked = routeApi({ 'GET /api/applications/forms': FORMS, 'POST /api/applications': makeApp({ id: 'app-3' }) })
    renderPage('/wnioski/nowy?form=ZAS-53')
    await screen.findByRole('radio', { name: /zasiłek chorobowy/i })
    expect(screen.queryByRole('radiogroup', { name: /którego dziecka dotyczy/i })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/applications', { method: 'POST', body: { form_code: 'ZAS-53' } }))
  })

  it('wniosek bez kreatora (np. z linku ze świadczenia) pokazuje wyjaśnienie i link do pustego formularza', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=BECIKOWE')
    const note = await screen.findByRole('note')
    expect(note).toHaveTextContent(/dla wniosku BECIKOWE nie mamy jeszcze kreatora/i)
    expect(screen.getByRole('link', { name: /pusty formularz/i })).toHaveAttribute('href', '/api/wnioski/BECIKOWE/pdf')
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeDisabled()
  })

  it('bez żadnego dziecka odsyła do zakładki Rodzina', async () => {
    const family = makeFamily(ANNA)
    family.children = []
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=ZAM', family)
    expect(await screen.findByRole('link', { name: 'Rodzina' })).toHaveAttribute('href', '/rodzina')
  })

  it('błąd tworzenia (np. dziecko w trybie straty) pokazuje komunikat z API', async () => {
    routeApi({
      'GET /api/applications/forms': FORMS,
      'POST /api/applications': new ApiError(409, 'Dla tego dziecka nie składamy już wniosków.'),
    })
    renderPage('/wnioski/nowy?form=ZAS-53')
    await userEvent.click(await screen.findByRole('button', { name: /zacznij wypełnianie/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Dla tego dziecka nie składamy już wniosków.')
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeEnabled()
  })
})
