import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import {
  ActionMenu,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardHeader,
  Checkbox,
  ConfirmDialog,
  CountBadge,
  Disclosure,
  EditableChip,
  EmptyState,
  IconButton,
  InfoTip,
  NewBadge,
  OptionCard,
  ProgressBar,
  RadioGroup,
  SearchInput,
  SectionHeader,
  SegmentedControl,
  Select,
  Stepper,
  SurveyStatusBadge,
  Table,
  Tabs,
  Tag,
  TagInput,
  TextArea,
  TextField,
  TOAST_MS,
  ToastProvider,
  ToggleChip,
  icons,
  useToast,
} from '.';

// --- Buttons ----------------------------------------------------------------

test('Button: variant class, no accidental submit, loading disables it', () => {
  const onClick = vi.fn();
  const { rerender } = render(
    <Button variant="primary" onClick={onClick}>
      Save
    </Button>,
  );
  const b = screen.getByRole('button', { name: 'Save' });
  expect(b).toHaveClass('btn', 'btn-primary');
  expect(b).toHaveAttribute('type', 'button');
  fireEvent.click(b);
  expect(onClick).toHaveBeenCalledTimes(1);

  rerender(
    <Button variant="danger" loading onClick={onClick}>
      Save
    </Button>,
  );
  expect(b).toBeDisabled();
  expect(b).toHaveAttribute('aria-busy', 'true');
  expect(b).toHaveClass('btn-danger');
});

test('ButtonLink is a real link styled as a button', () => {
  render(
    <MemoryRouter>
      <ButtonLink to="/templates" variant="secondary">
        Browse templates
      </ButtonLink>
    </MemoryRouter>,
  );
  const a = screen.getByRole('link', { name: 'Browse templates' });
  expect(a).toHaveAttribute('href', '/templates');
  expect(a).toHaveClass('btn-secondary');
});

test('IconButton is named by its label', () => {
  render(<IconButton label="Close" icon={icons.close} />);
  expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
});

// --- Card, badges, empty state --------------------------------------------

test('Card with header renders a heading and actions', () => {
  render(
    <Card aria-labelledby="t">
      <CardHeader id="t" title="Your surveys" actions={<Button>View all</Button>} />
    </Card>,
  );
  expect(screen.getByRole('region', { name: 'Your surveys' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { level: 2, name: 'Your surveys' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'View all' })).toBeInTheDocument();
});

test('SurveyStatusBadge maps API statuses to label and tone', () => {
  render(
    <>
      <SurveyStatusBadge status="live" />
      <SurveyStatusBadge status="draft" />
      <SurveyStatusBadge status="scheduled" />
      <SurveyStatusBadge status="closed" />
    </>,
  );
  expect(screen.getByText('Live')).toHaveClass('badge-positive');
  expect(screen.getByText('Draft')).toHaveClass('badge-neutral');
  expect(screen.getByText('Scheduled')).toHaveClass('badge-outline');
  expect(screen.getByText('Closed')).toHaveClass('badge-muted');
});

test('Badge, CountBadge and NewBadge', () => {
  render(
    <>
      <Badge tone="negative">Detractor</Badge>
      <CountBadge count={3} label="3 new contact requests" />
      <NewBadge />
    </>,
  );
  expect(screen.getByText('Detractor')).toHaveClass('badge-negative');
  expect(screen.getByLabelText('3 new contact requests')).toHaveTextContent('3');
  expect(screen.getByText('New')).toHaveClass('new-badge');
});

test('EmptyState shows title, text and actions', () => {
  render(<EmptyState icon={icons.list} title="No surveys yet" text="Create one." actions={<Button>Create survey</Button>} />);
  expect(screen.getByText('No surveys yet')).toBeInTheDocument();
  expect(screen.getByText('Create one.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Create survey' })).toBeInTheDocument();
});

// --- Form fields ------------------------------------------------------------

test('TextField links label, hint and error', () => {
  render(<TextField label="Survey title" hint="Shown to readers" error="Title is required" required />);
  const input = screen.getByRole('textbox', { name: /Survey title/ });
  expect(input).toBeRequired();
  expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(input).toHaveAccessibleDescription('Shown to readers Title is required');
  expect(screen.getByRole('alert')).toHaveTextContent('Title is required');
});

test('TextArea and Select are labelled', () => {
  render(
    <>
      <TextArea label="Description" />
      <Select
        label="Language"
        options={[
          { value: 'en', label: 'English' },
          { value: 'fi', label: 'Finnish' },
        ]}
        defaultValue="fi"
      />
    </>,
  );
  expect(screen.getByRole('textbox', { name: 'Description' })).toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Language' })).toHaveValue('fi');
});

test('Checkbox and RadioGroup', () => {
  const onRadio = vi.fn();
  render(
    <>
      <Checkbox label="Required" defaultChecked />
      <RadioGroup
        legend="Answers"
        name="anon"
        value="anonymous"
        onChange={onRadio}
        options={[
          { value: 'anonymous', label: 'Anonymous' },
          { value: 'identified', label: 'Identified' },
        ]}
      />
    </>,
  );
  expect(screen.getByRole('checkbox', { name: 'Required' })).toBeChecked();
  expect(screen.getByRole('group', { name: 'Answers' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio', { name: 'Identified' }));
  expect(onRadio).toHaveBeenCalledWith('identified');
});

test('SearchInput searches on Enter and on the button', () => {
  const onSearch = vi.fn();
  function Demo() {
    const [q, setQ] = useState('');
    return <SearchInput label="Search surveys" value={q} onChange={setQ} onSearch={onSearch} />;
  }
  render(<Demo />);
  const box = screen.getByRole('searchbox', { name: 'Search surveys' });
  fireEvent.change(box, { target: { value: 'nps' } });
  fireEvent.keyDown(box, { key: 'Enter' });
  fireEvent.click(screen.getByRole('button', { name: 'Search surveys' }));
  expect(onSearch).toHaveBeenNthCalledWith(1, 'nps');
  expect(onSearch).toHaveBeenNthCalledWith(2, 'nps');
});

// --- Chips and tags ---------------------------------------------------------

test('ToggleChip toggles aria-pressed', () => {
  const onChange = vi.fn();
  render(
    <ToggleChip selected={false} onChange={onChange}>
      Too long
    </ToggleChip>,
  );
  const chip = screen.getByRole('button', { name: 'Too long' });
  expect(chip).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(chip);
  expect(onChange).toHaveBeenCalledWith(true);
});

test('EditableChip edits and removes', () => {
  const onChange = vi.fn();
  const onRemove = vi.fn();
  render(<EditableChip label="Reason 1" value="Price" onChange={onChange} onRemove={onRemove} />);
  fireEvent.change(screen.getByRole('textbox', { name: 'Reason 1' }), { target: { value: 'Prices' } });
  expect(onChange).toHaveBeenCalledWith('Prices');
  fireEvent.click(screen.getByRole('button', { name: 'Remove Reason 1' }));
  expect(onRemove).toHaveBeenCalled();
});

test('Tag and TagInput add with Enter and remove with ×', () => {
  function Demo() {
    const [tags, setTags] = useState(['newsletter']);
    return <TagInput label="Segment tags" values={tags} onChange={setTags} />;
  }
  render(
    <>
      <Tag>Finland</Tag>
      <Demo />
    </>,
  );
  expect(screen.getByText('Finland')).toHaveClass('tag');
  const input = screen.getByRole('textbox', { name: 'Segment tags' });
  fireEvent.change(input, { target: { value: 'members' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(screen.getByText('members')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Remove newsletter' }));
  expect(screen.queryByText('newsletter')).not.toBeInTheDocument();
});

// --- Tabs, segmented control, stepper, option card ---------------------------

test('Tabs: click and arrow keys change the tab, only the selected one is tabbable', () => {
  function Demo() {
    const [tab, setTab] = useState('summary');
    return (
      <Tabs
        label="Result views"
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'summary', label: 'In short' },
          { id: 'reasons', label: 'Reasons' },
          { id: 'comments', label: 'Comments' },
        ]}
      >
        <p>Panel {tab}</p>
      </Tabs>
    );
  }
  render(<Demo />);
  const first = screen.getByRole('tab', { name: 'In short' });
  expect(first).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: 'Reasons' })).toHaveAttribute('tabindex', '-1');

  fireEvent.keyDown(first, { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: 'Reasons' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: 'Reasons' })).toHaveFocus();

  fireEvent.keyDown(screen.getByRole('tab', { name: 'Reasons' }), { key: 'End' });
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel comments');

  fireEvent.click(first);
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel summary');
});

test('SegmentedControl marks the chosen option', () => {
  const onChange = vi.fn();
  render(
    <SegmentedControl
      label="Status"
      value="all"
      onChange={onChange}
      options={[
        { value: 'all', label: 'All' },
        { value: 'live', label: 'Live' },
      ]}
    />,
  );
  expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'Live' }));
  expect(onChange).toHaveBeenCalledWith('live');
});

test('Stepper: done steps are clickable, future steps are disabled', () => {
  const onSelect = vi.fn();
  render(
    <Stepper
      current="build"
      onSelect={onSelect}
      steps={[
        { id: 'type', label: 'Type' },
        { id: 'build', label: 'Build' },
        { id: 'share', label: 'Share' },
      ]}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: /Type/ }));
  expect(onSelect).toHaveBeenCalledWith('type');
  expect(screen.getByRole('button', { name: /Build/ })).toHaveAttribute('aria-current', 'step');
  expect(screen.getByRole('button', { name: /Share/ })).toBeDisabled();
});

test('OptionCard is a button with its title as name', () => {
  const onClick = vi.fn();
  render(<OptionCard title="NPS" description="0 to 10" selected onClick={onClick} />);
  const card = screen.getByRole('button', { name: /NPS/ });
  expect(card).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(card);
  expect(onClick).toHaveBeenCalled();
});

// --- Small pieces -------------------------------------------------------------

test('ProgressBar, SectionHeader, Disclosure, InfoTip', () => {
  render(
    <>
      <ProgressBar label="Responses toward the limit" value={30} max={120} />
      <SectionHeader>Advanced</SectionHeader>
      <Disclosure title="Branding">
        <p>Logo settings</p>
      </Disclosure>
      <InfoTip label="What is NPS?">Net Promoter Score</InfoTip>
    </>,
  );
  expect(screen.getByRole('progressbar', { name: 'Responses toward the limit' })).toHaveAttribute('aria-valuenow', '30');
  expect(screen.getByRole('heading', { name: 'Advanced' })).toBeInTheDocument();

  const toggle = screen.getByRole('button', { name: 'Branding' });
  expect(screen.getByText('Logo settings')).not.toBeVisible();
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('Logo settings')).toBeVisible();

  expect(screen.getByRole('button', { name: 'What is NPS?' })).toHaveAccessibleDescription('Net Promoter Score');
});

// --- Menu, dialog, toast, table ------------------------------------------------

test('ActionMenu opens, moves with arrows, runs an item, and Escape returns focus', () => {
  const onDelete = vi.fn();
  render(
    <ActionMenu
      label="Actions for Member NPS"
      items={[
        { label: 'Edit', onSelect: vi.fn() },
        { label: 'Delete', onSelect: onDelete, danger: true },
      ]}
    />,
  );
  const trigger = screen.getByRole('button', { name: 'Actions for Member NPS' });
  fireEvent.click(trigger);
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('menuitem', { name: 'Edit' })).toHaveFocus();

  fireEvent.keyDown(screen.getByRole('menu'), { key: 'ArrowDown' });
  expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveFocus();

  fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' });
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();

  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
  expect(onDelete).toHaveBeenCalled();
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
});

test('ConfirmDialog: focus on Cancel, Escape cancels, confirm runs', () => {
  const onCancel = vi.fn();
  const onConfirm = vi.fn();
  render(
    <ConfirmDialog open title="Delete “Member NPS”?" confirmLabel="Delete survey" danger onConfirm={onConfirm} onCancel={onCancel}>
      Its answers are deleted too.
    </ConfirmDialog>,
  );
  const dialog = screen.getByRole('alertdialog', { name: 'Delete “Member NPS”?' });
  expect(dialog).toHaveAccessibleDescription('Its answers are deleted too.');
  expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

  fireEvent.keyDown(dialog, { key: 'Escape' });
  expect(onCancel).toHaveBeenCalled();

  const confirm = screen.getByRole('button', { name: 'Delete survey' });
  expect(confirm).toHaveClass('btn-danger');
  fireEvent.click(confirm);
  expect(onConfirm).toHaveBeenCalled();
});

test('Toast shows a message in a status region and hides it after a while', () => {
  vi.useFakeTimers();
  function Demo() {
    const toast = useToast();
    return <Button onClick={() => toast('Survey saved')}>Save</Button>;
  }
  render(
    <ToastProvider>
      <Demo />
    </ToastProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(screen.getByRole('status')).toHaveTextContent('Survey saved');
  act(() => {
    vi.advanceTimersByTime(TOAST_MS + 10);
  });
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  vi.useRealTimers();
});

test('Table renders a caption, headers, rows and the empty message', () => {
  type Row = { id: string; name: string; answers: number };
  const columns = [
    { key: 'name', header: 'Survey' },
    { key: 'answers', header: 'Responses', numeric: true },
  ];
  const { rerender } = render(
    <Table<Row>
      caption="Your surveys"
      columns={columns}
      rowKey={(r) => r.id}
      rows={[{ id: '1', name: 'Member NPS', answers: 132 }]}
    />,
  );
  expect(screen.getByRole('table', { name: 'Your surveys' })).toBeInTheDocument();
  expect(screen.getByRole('columnheader', { name: 'Responses' })).toHaveClass('num');
  expect(screen.getByRole('cell', { name: '132' })).toHaveAttribute('data-label', 'Responses');

  rerender(<Table<Row> caption="Your surveys" columns={columns} rowKey={(r) => r.id} rows={[]} empty="No surveys yet" />);
  expect(screen.getByRole('cell', { name: 'No surveys yet' })).toBeInTheDocument();
});
