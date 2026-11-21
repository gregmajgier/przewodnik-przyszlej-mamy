import type { FamilyView, User } from '../../lib/types'
import type { Application, FormsResponse } from './types'

export const ANNA_ID = 'user-nowak-anna'
export const PIOTR: User = {
  id: 'user-nowak-piotr',
  role: 'parent',
  name: 'Piotr Nowak',
  email: null,
  persona_id: 'persona-nowak-piotr',
  family_id: 'f1',
  unit_id: null,
}

export function makeFamily(anna: User): FamilyView {
  return {
    family: { id: 'f1', name: 'Nowak', owner_id: anna.id, member_ids: [anna.id, PIOTR.id], invite_code: null, invite_expires_at: null },
    members: [anna, PIOTR],
    children: [
      { id: 'c-maja', family_id: 'f1', name: 'Maja', birth_date: '2019-05-01', due_date: null, status: 'born', pesel: null, has_disability: false, foster: false, situation: null, situation_kind: null, situation_at: null, serious_illness: false },
      { id: 'c-drodze', family_id: 'f1', name: 'Dziecko w drodze', birth_date: null, due_date: '2027-01-20', status: 'expected', pesel: null, has_disability: false, foster: false, situation: null, situation_kind: null, situation_at: null, serious_illness: false },
      { id: 'c-lost', family_id: 'f1', name: 'Utracone', birth_date: null, due_date: '2026-12-01', status: 'expected', pesel: null, has_disability: false, foster: false, situation: 'loss', situation_kind: 'poronienie', situation_at: null, serious_illness: false },
    ],
    pending_requests: [],
  }
}

export const FIELDS = [
  { id: 'first_name', label: 'Imię', type: 'text', required: true, choices: null },
  { id: 'employer_name', label: 'Nazwa pracodawcy', type: 'text', required: true, choices: null },
  { id: 'leave_start', label: 'Początek urlopu macierzyńskiego', type: 'date', required: true, choices: null },
  { id: 'employer_email', label: 'Adres e-mail pracodawcy (dział kadr)', type: 'text', required: false, choices: null },
] as const

export function makeApp(over: Partial<Application> = {}): Application {
  return {
    id: 'app-1',
    family_id: 'f1',
    applicant_id: ANNA_ID,
    form_code: 'URLOP-MAC-ROD',
    child_id: 'c-drodze',
    channel: 'employer_email',
    status: 'draft',
    values: { first_name: 'Anna', employer_name: 'Krakowskie Centrum Usług Wspólnych', leave_start: '2027-01-20', employer_email: 'kadry@kcuw.example.pl' },
    missing: [],
    recipient_email: 'kadry@kcuw.example.pl',
    recipient_domain: 'kcuw.example.pl',
    thread_id: null,
    signed_at: null,
    sent_at: null,
    created_at: '2026-11-21T10:00:00Z',
    fields: FIELDS.map((f) => ({ ...f })),
    ...over,
  }
}

export const FORMS: FormsResponse = {
  recommended_flow: ['URLOP-MAC-ROD', 'ZAM'],
  forms: [
    { code: 'URLOP-MAC-ROD', name: 'Wniosek o urlop macierzyński i rodzicielski', institution: 'pracodawca', deadline: 'do 21 dni po porodzie', channels: ['employer_email', 'pdf_download'], default_channel: 'employer_email', only_electronic: false, requires_child: true, portal_id: null },
    { code: 'ZAM', name: 'Wniosek o zasiłek macierzyński', institution: 'ZUS', deadline: null, channels: ['portal_agent', 'pdf_download'], default_channel: 'portal_agent', only_electronic: false, requires_child: true, portal_id: 'ezus_zam' },
    { code: '800PLUS', name: 'Świadczenie wychowawcze 800+', institution: 'ZUS', deadline: null, channels: ['portal_agent'], default_channel: 'portal_agent', only_electronic: true, requires_child: true, portal_id: 'ezus_800plus' },
    { code: 'ZAS-53', name: 'Wniosek o zasiłek chorobowy', institution: 'ZUS', deadline: null, channels: ['pdf_download'], default_channel: 'pdf_download', only_electronic: false, requires_child: false, portal_id: null },
  ],
}
