-- migrate:up
-- The prototype's survey types are thumbs, NPS, CSAT and "start from scratch".
-- "poll" was a placeholder for the thumbs rating; "custom" is start from scratch.
alter type survey_type rename value 'poll' to 'thumbs';

-- migrate:down
alter type survey_type rename value 'thumbs' to 'poll';
