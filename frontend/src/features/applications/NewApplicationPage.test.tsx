import { screen, waitFor } from '@testing-library/react'
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
  it('pokazuje listę wniosków z oznaczeniem polecanych', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage()
    expect(await screen.findByRole('option', { name: /urlop macierzyński i rodzicielski \(polecany\)/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /zasiłek macierzyński \(polecany\)/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /800\+$/ })).toBeInTheDocument() // niepolecany: bez dopisku
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeDisabled()
  })

  it('kod z adresu (?form=) wybiera wniosek; dziecko jest wymagane i bez straty', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=ZAM')
    const child = await screen.findByLabelText(/dziecko, którego dotyczy wniosek/i)
    expect(screen.getByLabelText('Rodzaj wniosku')).toHaveValue('ZAM')
    expect(screen.getByRole('option', { name: /Maja \(ur\. 01\.05\.2019\)/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Dziecko w drodze \(w drodze, termin porodu 20\.01\.2027\)/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Utracone/ })).not.toBeInTheDocument() // tryb straty: bez wniosków
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeDisabled() // dziecko niewybrane
    await userEvent.selectOptions(child, 'c-drodze')
    expect(screen.getByRole('button', { name: /zacznij wypełnianie/i })).toBeEnabled()
  })

  it('zakłada wniosek z dzieckiem i wybranym kanałem, potem przechodzi do kreatora', async () => {
    const mocked = routeApi({
      'GET /api/applications/forms': FORMS,
      'POST /api/applications': makeApp({ id: 'app-77', form_code: 'ZAM', channel: 'pdf_download' }),
    })
    renderPage('/wnioski/nowy?form=ZAM')
    await userEvent.selectOptions(await screen.findByLabelText(/dziecko, którego dotyczy wniosek/i), 'c-drodze')
    expect(screen.getByLabelText(/agent wypełnia makietę portalu/i)).toBeChecked() // kanał domyślny
    await userEvent.click(screen.getByLabelText(/pdf do pobrania/i))
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications', {
        method: 'POST',
        body: { form_code: 'ZAM', child_id: 'c-drodze', channel: 'pdf_download' },
      }),
    )
    expect(await screen.findByText('Kreator wniosku')).toBeInTheDocument()
  })

  it('jedno dziecko do wyboru jest wybierane automatycznie, a pojedynczy kanał nie jest wysyłany', async () => {
    const family = makeFamily(ANNA)
    family.children = [family.children[0]]
    const mocked = routeApi({ 'GET /api/applications/forms': FORMS, 'POST /api/applications': makeApp({ id: 'app-2' }) })
    renderPage('/wnioski/nowy?form=800PLUS', family)
    expect(await screen.findByText(/składa się wyłącznie elektronicznie/i)).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /jak złożyć wniosek/i })).not.toBeInTheDocument() // jeden kanał
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications', { method: 'POST', body: { form_code: '800PLUS', child_id: 'c-maja' } }),
    )
  })

  it('wniosek bez dziecka (np. zasiłek chorobowy) nie pyta o dziecko', async () => {
    const mocked = routeApi({ 'GET /api/applications/forms': FORMS, 'POST /api/applications': makeApp({ id: 'app-3' }) })
    renderPage('/wnioski/nowy?form=ZAS-53')
    await screen.findByLabelText('Rodzaj wniosku')
    expect(screen.queryByLabelText(/dziecko, którego dotyczy wniosek/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /zacznij wypełnianie/i }))
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/applications', { method: 'POST', body: { form_code: 'ZAS-53' } }))
  })

  it('wniosek bez kreatora (np. z linku ze świadczenia) pokazuje wyjaśnienie i link do pustego formularza', async () => {
    routeApi({ 'GET /api/applications/forms': FORMS })
    renderPage('/wnioski/nowy?form=BECIKOWE')
    const note = await screen.findByRole('note')
    expect(note).toHaveTextContent(/dla wniosku BECIKOWE nie ma jeszcze kreatora/i)
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

  it('bez rodziny przekierowuje na /start', async () => {
    routeApi({})
    renderPage('/wnioski/nowy', null)
    expect(await screen.findByText('Start')).toBeInTheDocument()
  })
})
