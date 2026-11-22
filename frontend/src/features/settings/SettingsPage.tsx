import { PageHeader } from '../../components/PageHeader';
import { Card, CardBody, CardHeader, Switch, useToast } from '../../components/ui';
import { FEATURE_FLAGS, useFeatureFlag, type FeatureFlag } from './featureFlags';
import './settings.css';

function FlagSwitch({ flag }: { flag: FeatureFlag }) {
  const toast = useToast();
  const [on, setOn] = useFeatureFlag(flag);
  const { label, description } = FEATURE_FLAGS[flag];
  return (
    <Switch
      label={label}
      description={description}
      checked={on}
      onChange={(value) => {
        if (!setOn(value)) toast('Your browser did not let us save this. It applies until you reload the page.');
      }}
    />
  );
}

/** Settings (#153). For now only the feature flags. */
export function SettingsPage() {
  return (
    <div className="settings-page">
      <PageHeader title="Settings" description="Choose what you see in LianaSurvey." />
      <Card aria-labelledby="feature-flags-title">
        <CardHeader id="feature-flags-title" title="Feature flags" />
        <CardBody className="settings-flags">
          <p className="settings-hint">Turn optional parts of LianaSurvey on or off.</p>
          {(Object.keys(FEATURE_FLAGS) as FeatureFlag[]).map((flag) => (
            <FlagSwitch key={flag} flag={flag} />
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
