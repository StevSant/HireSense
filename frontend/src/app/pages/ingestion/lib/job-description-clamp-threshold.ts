/**
 * Minimum description length (characters) before a collapsible
 * JobDescriptionComponent clamps its height behind a "Show full description"
 * toggle. Roughly one viewport of rendered text — shorter descriptions render
 * in full since clamping them would hide only a line or two.
 */
export const JOB_DESCRIPTION_CLAMP_THRESHOLD = 1200;
