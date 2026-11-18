import { slug } from './slug';

test('survey names become lower-case tags', () => {
  expect(slug('Member NPS 2026')).toBe('member-nps-2026');
  expect(slug('  Kesä/Summer -- feedback! ')).toBe('kesa-summer-feedback');
});

test('Finnish and Swedish letters keep their base letter', () => {
  expect(slug('Jäsenkysely')).toBe('jasenkysely');
  expect(slug('Öppna frågor')).toBe('oppna-fragor');
});

test('tags are at most 40 characters and never empty', () => {
  expect(slug('x'.repeat(80))).toHaveLength(40);
  expect(slug(`${'a'.repeat(39)} b`)).toBe('a'.repeat(39));
  expect(slug('???')).toBe('campaign');
});
