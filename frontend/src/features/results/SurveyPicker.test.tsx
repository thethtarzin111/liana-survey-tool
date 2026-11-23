import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import type { SurveyListItem } from '../../api/client';
import { SurveyPicker } from './SurveyPicker';

function survey(id: string, title: string, overrides: Partial<SurveyListItem> = {}): SurveyListItem {
  return {
    id, title, description: null, thank_you: null, type: 'nps', status: 'live', opens_at: null, closes_at: null,
    answers: 0, last_answer_at: null, created_at: '2026-11-01T09:00:00Z', updated_at: '2026-11-01T09:00:00Z', headline: null, comment_field: true, show_results: true, contact_opt_in: true,
    accent_color: 'x', background_color: 'y', logo_url: null, ...overrides,
  };
}
const surveys = [
  survey('a', 'Member NPS 2026', { answers: 132 }),
  survey('b', 'Course feedback', { type: 'csat', status: 'closed', answers: 1 }),
  survey('c', 'Newsletter thumbs', { type: 'thumbs', status: 'draft' }),
];

function Harness({ onPick = () => {} }: { onPick?: (id: string) => void }) {
  const [value, setValue] = useState('a');
  return (
    <SurveyPicker
      surveys={surveys}
      value={value}
      onPick={(id) => {
        setValue(id);
        onPick(id);
      }}
    />
  );
}

const open = () => fireEvent.click(screen.getByRole('button', { name: /Survey/ }));

test('lists surveys with type, answers and status', () => {
  render(<Harness />);
  const button = screen.getByRole('button', { name: /Survey/ });
  expect(button).toHaveTextContent('Member NPS 2026');
  expect(button).toHaveTextContent('NPS survey · Live');
  open();
  const options = within(screen.getByRole('listbox', { name: 'Surveys' })).getAllByRole('option');
  expect(options).toHaveLength(3);
  expect(options[0]).toHaveTextContent('Member NPS 2026');
  expect(options[0]).toHaveTextContent('NPS survey · 132 answers');
  expect(options[0]).toHaveAttribute('aria-selected', 'true');
  expect(options[1]).toHaveTextContent('CSAT survey · 1 answer');
  expect(options[1]).toHaveTextContent('Closed');
  expect(options[2]).toHaveAttribute('aria-selected', 'false');
  expect(options[2]).toHaveTextContent('Draft');
});

test('search filters and shows "No surveys match “x”."', () => {
  render(<Harness />);
  open();
  const search = screen.getByRole('combobox', { name: 'Search surveys' });
  fireEvent.change(search, { target: { value: 'COURSE' } });
  expect(screen.getAllByRole('option')).toHaveLength(1);
  expect(screen.getByRole('option')).toHaveTextContent('Course feedback');
  fireEvent.change(search, { target: { value: 'zzz' } });
  expect(screen.queryByRole('option')).not.toBeInTheDocument();
  expect(screen.getByText('No surveys match “zzz”.')).toBeInTheDocument();
});

test('arrow keys and Enter pick, Escape closes', () => {
  const onPick = vi.fn();
  render(<Harness onPick={onPick} />);
  open();
  const search = screen.getByRole('combobox', { name: 'Search surveys' });
  fireEvent.keyDown(search, { key: 'ArrowDown' });
  fireEvent.keyDown(search, { key: 'ArrowDown' });
  expect(search).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[2].id);
  fireEvent.keyDown(search, { key: 'ArrowUp' });
  fireEvent.keyDown(search, { key: 'Enter' });
  expect(onPick).toHaveBeenCalledWith('b');
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Survey/ })).toHaveTextContent('Course feedback');
  expect(screen.getByRole('button', { name: /Survey/ })).toHaveFocus();

  open();
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Search surveys' }), { key: 'Escape' });
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Survey/ })).toHaveFocus();
  expect(onPick).toHaveBeenCalledTimes(1);
});

test('clicking a survey picks it', () => {
  const onPick = vi.fn();
  render(<Harness onPick={onPick} />);
  open();
  fireEvent.click(screen.getByRole('option', { name: /Newsletter thumbs/ }));
  expect(onPick).toHaveBeenCalledWith('c');
});

test('focus moves to the search field when opened', () => {
  render(<Harness />);
  expect(screen.getByRole('button', { name: /Survey/ })).toHaveAttribute('aria-expanded', 'false');
  open();
  expect(screen.getByRole('button', { name: /Survey/ })).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('combobox', { name: 'Search surveys' })).toHaveFocus();
});

test('the search field is a combobox for the listbox and names the highlighted option', () => {
  render(<Harness />);
  open();
  const input = screen.getByRole('combobox', { name: 'Search surveys' });
  const list = screen.getByRole('listbox', { name: 'Surveys' });
  expect(input).toHaveAttribute('aria-controls', list.id);
  expect(input).toHaveAttribute('aria-expanded', 'true');
  expect(input).toHaveAttribute('aria-autocomplete', 'list');
  fireEvent.keyDown(input, { key: 'ArrowDown' });
  expect(input).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[1].id);
});

test('the highlighted option scrolls into view with the arrow keys', () => {
  const scroll = vi.fn();
  Element.prototype.scrollIntoView = scroll;
  try {
    render(<Harness />);
    open();
    scroll.mockClear();
    fireEvent.keyDown(screen.getByRole('combobox', { name: 'Search surveys' }), { key: 'ArrowDown' });
    expect(scroll).toHaveBeenCalledWith({ block: 'nearest' });
    expect(scroll.mock.contexts[0]).toBe(screen.getAllByRole('option')[1]);
  } finally {
    // @ts-expect-error jsdom has no scrollIntoView
    delete Element.prototype.scrollIntoView;
  }
});

test('the trigger opens a dialog named "Choose a survey" that holds the combobox', () => {
  render(<Harness />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  open();
  const dialog = screen.getByRole('dialog', { name: 'Choose a survey' });
  expect(within(dialog).getByRole('combobox', { name: 'Search surveys' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Survey/ })).toHaveAttribute('aria-haspopup', 'dialog');
});
