// Dev-only preview of the shared UI components (http://localhost:4200/dev/components).
// Not in the sidebar and not in production builds: App.tsx only adds the route
// when import.meta.env.DEV is true.
import { useState, type ReactNode } from 'react';
import { PageHeader } from '../components/PageHeader';
import {
  ActionMenu,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  ConfirmDialog,
  CountBadge,
  Disclosure,
  EditableChip,
  EmptyState,
  IconButton,
  InfoTip,
  LiveIndicator,
  List,
  ListItem,
  NewBadge,
  OptionCard,
  ProgressBar,
  RadioGroup,
  SearchInput,
  SectionHeader,
  SegmentedControl,
  Select,
  SentimentBadge,
  Stepper,
  SurveyStatusBadge,
  Table,
  Tabs,
  Tag,
  TagInput,
  TextArea,
  TextButton,
  TextField,
  ToggleChip,
  icons,
  useToast,
} from '../components/ui';

type Row = { id: string; name: string; status: 'live' | 'draft' | 'scheduled' | 'closed'; answers: number };

const rows: Row[] = [
  { id: '1', name: 'Member NPS 2026', status: 'live', answers: 132 },
  { id: '2', name: 'Spring event feedback', status: 'draft', answers: 0 },
  { id: '3', name: 'Course satisfaction', status: 'scheduled', answers: 0 },
  { id: '4', name: 'Newsletter thumbs', status: 'closed', answers: 2140 },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card aria-label={title} style={{ marginBottom: 16 }}>
      <CardHeader title={title} />
      <CardBody style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>{children}</CardBody>
    </Card>
  );
}

export function ComponentsPage() {
  const toast = useToast();
  const [tab, setTab] = useState('summary');
  const [seg, setSeg] = useState('all');
  const [chip, setChip] = useState(true);
  const [reason, setReason] = useState('Too long');
  const [tags, setTags] = useState(['newsletter', 'members']);
  const [anon, setAnon] = useState('anonymous');
  const [q, setQ] = useState('');
  const [dialog, setDialog] = useState(false);
  const [type, setType] = useState('nps');

  return (
    <>
      <PageHeader title="Shared UI components" description="Dev only. Every component from components/ui with Liana's tokens." />

      <Section title="Buttons">
        <Button variant="primary" icon={icons.plus}>
          Create survey
        </Button>
        <Button variant="secondary">View all</Button>
        <Button variant="ghost">Reset</Button>
        <Button variant="dark">Publish</Button>
        <Button variant="danger">Delete</Button>
        <Button variant="secondary" size="sm">
          Small
        </Button>
        <Button variant="primary" loading>
          Saving
        </Button>
        <Button variant="primary" disabled>
          Disabled
        </Button>
        <IconButton label="Copy link" icon={icons.copy} />
        <TextButton>Text action</TextButton>
      </Section>

      <Section title="Badges">
        <SurveyStatusBadge status="live" />
        <SurveyStatusBadge status="draft" />
        <SurveyStatusBadge status="scheduled" />
        <SurveyStatusBadge status="closed" />
        <SentimentBadge sentiment="negative">Detractor</SentimentBadge>
        <SentimentBadge sentiment="neutral">Passive</SentimentBadge>
        <SentimentBadge sentiment="positive">Promoter</SentimentBadge>
        <Badge tone="outline">Outline</Badge>
        <CountBadge count={3} label="3 new" />
        <NewBadge />
        <LiveIndicator>Live · updated just now</LiveIndicator>
      </Section>

      <Section title="Form fields">
        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', width: '100%' }}>
          <TextField label="Survey title" required placeholder="Untitled survey" hint="Readers see this at the top." />
          <TextField label="With an error" error="Title is required" />
          <TextArea label="Description" placeholder="Members' opinions about the spring course" />
          <Select
            label="Language"
            options={[
              { value: 'en', label: 'English' },
              { value: 'fi', label: 'Finnish' },
              { value: 'sv', label: 'Swedish' },
            ]}
          />
          <SearchInput label="Search surveys" value={q} onChange={setQ} onSearch={(v) => toast(`Search: ${v}`)} />
          <TagInput label="Segment tags" values={tags} onChange={setTags} placeholder="Add a tag…" />
          <Checkbox label="Required" hint="Readers must answer this question" defaultChecked />
          <RadioGroup
            legend="Answers are"
            name="anon"
            value={anon}
            onChange={setAnon}
            options={[
              { value: 'anonymous', label: 'Anonymous', hint: 'No name or email is stored with the answer' },
              { value: 'identified', label: 'Identified', hint: 'Only after the reader opts in' },
            ]}
          />
        </div>
      </Section>

      <Section title="Chips and tags">
        <ToggleChip selected={chip} onChange={setChip}>
          Toggle chip
        </ToggleChip>
        <EditableChip label="Reason 1" value={reason} onChange={setReason} onRemove={() => toast('Removed')} />
        <Tag>Finland: online media</Tag>
        <Tag onRemove={() => toast('Removed')} removeLabel="Remove Newsletter">
          Newsletter
        </Tag>
      </Section>

      <Section title="Navigation">
        <div style={{ width: '100%' }}>
          <Stepper
            current="build"
            steps={[
              { id: 'type', label: 'What to find out' },
              { id: 'build', label: 'Build your survey' },
              { id: 'follow', label: 'Follow up' },
              { id: 'share', label: 'Share' },
            ]}
          />
        </div>
        <SegmentedControl
          label="Status filter"
          value={seg}
          onChange={setSeg}
          options={[
            { value: 'all', label: 'All' },
            { value: 'live', label: 'Live' },
            { value: 'draft', label: 'Draft' },
          ]}
        />
        <div style={{ width: '100%' }}>
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
            <p>Selected tab: {tab}</p>
          </Tabs>
        </div>
      </Section>

      <Section title="Option cards">
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', width: '100%' }}>
          {[
            ['thumbs', 'Thumbs rating', 'Was this useful? One tap.'],
            ['nps', 'NPS', 'How likely to recommend, 0 to 10.'],
            ['csat', 'CSAT', 'How satisfied, 1 to 5.'],
            ['custom', 'Start from scratch', 'Your own questions.'],
          ].map(([id, title, text]) => (
            <OptionCard key={id} icon={icons.chart} title={title} description={text} selected={type === id} onClick={() => setType(id)} />
          ))}
        </div>
      </Section>

      <Section title="Table, menu and dialog">
        <div style={{ width: '100%' }}>
          <Table<Row>
            caption="Example surveys"
            rows={rows}
            rowKey={(r) => r.id}
            columns={[
              { key: 'name', header: 'Survey' },
              { key: 'status', header: 'Status', render: (r) => <SurveyStatusBadge status={r.status} /> },
              { key: 'answers', header: 'Responses', numeric: true },
              {
                key: 'actions',
                header: 'Actions',
                hideHeader: true,
                render: (r) => (
                  <ActionMenu
                    label={`Actions for ${r.name}`}
                    items={[
                      { label: 'Edit', icon: icons.edit, onSelect: () => toast(`Edit ${r.name}`) },
                      { label: 'Duplicate', icon: icons.copy, onSelect: () => toast(`Duplicated ${r.name}`) },
                      { label: 'Delete', icon: icons.trash, danger: true, onSelect: () => setDialog(true) },
                    ]}
                  />
                ),
              },
            ]}
          />
        </div>
        <ConfirmDialog
          open={dialog}
          title="Delete “Member NPS 2026”?"
          confirmLabel="Delete survey"
          danger
          onCancel={() => setDialog(false)}
          onConfirm={() => {
            setDialog(false);
            toast('Survey deleted');
          }}
        >
          Its 132 answers are deleted too. This can’t be undone.
        </ConfirmDialog>
        <Button onClick={() => toast('Survey saved')}>Show a toast</Button>
      </Section>

      <Section title="Other">
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <SectionHeader>Section header</SectionHeader>
          <ProgressBar label="Responses toward the limit" value={40} max={100} />
          <p style={{ margin: 0 }}>
            Info tip
            <InfoTip label="What is NPS?">Net Promoter Score: the share of promoters (9–10) minus detractors (0–6).</InfoTip>
          </p>
          <Card>
            <Disclosure title="Branding">
              <p style={{ margin: 0 }}>Logo and colours go here.</p>
            </Disclosure>
          </Card>
          <Card>
            <List label="Example list">
              <ListItem>First row</ListItem>
              <ListItem>Second row</ListItem>
            </List>
          </Card>
          <Card>
            <EmptyState
              icon={icons.list}
              title="No surveys yet"
              text="Create a survey from a template in a couple of minutes, or build your own."
              actions={
                <>
                  <Button variant="primary" icon={icons.plus}>
                    Create survey
                  </Button>
                  <Button variant="secondary">Browse templates</Button>
                </>
              }
            />
          </Card>
        </div>
      </Section>
    </>
  );
}
