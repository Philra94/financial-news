import { useEffect, useState } from 'react'

import { getSettings, putSettings } from '../lib/api'
import type { AppSettings } from '../types'

const EMPTY_SETTINGS: AppSettings = {
  youtube: {
    api_key: '',
    channels: [],
    max_videos_per_channel: 5,
    lookback_hours: 24,
  },
  agent: {
    backend: 'codex',
    max_concurrent_research: 2,
    research_timeout_seconds: 600,
  },
  schedule: {
    fetch_cron: '0 5 * * *',
    timezone: 'Europe/Berlin',
  },
  site: {
    title: 'Morning Briefing',
    subtitle: 'Local agentic financial news',
    accent_color: '#C0392B',
  },
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(EMPTY_SETTINGS)
  const [channelDraft, setChannelDraft] = useState({ id: '', name: '', focus: '' })
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    getSettings().then(setSettings)
  }, [])

  function updateField<T extends keyof AppSettings>(key: T, value: AppSettings[T]) {
    setSettings((current) => ({ ...current, [key]: value }))
  }

  function addChannel() {
    if (!channelDraft.id || !channelDraft.name) {
      return
    }
    updateField('youtube', {
      ...settings.youtube,
      channels: settings.youtube.channels.concat({
        id: channelDraft.id,
        name: channelDraft.name,
        focus: channelDraft.focus
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
      }),
    })
    setChannelDraft({ id: '', name: '', focus: '' })
  }

  function removeChannel(channelId: string) {
    updateField('youtube', {
      ...settings.youtube,
      channels: settings.youtube.channels.filter((channel) => channel.id !== channelId),
    })
  }

  async function save() {
    const saved = await putSettings(settings)
    setSettings(saved)
    setNote('Settings saved.')
  }

  return (
    <section>
      <div className="section-label">Settings</div>
      <h1 className="briefing-title">Configuration</h1>

      <div className="settings-form">
        <label className="field">
          <span>Site title</span>
          <input
            value={settings.site.title}
            onChange={(event) => updateField('site', { ...settings.site, title: event.target.value })}
          />
        </label>

        <label className="field">
          <span>YouTube Data API key</span>
          <input
            type="password"
            value={settings.youtube.api_key}
            onChange={(event) =>
              updateField('youtube', { ...settings.youtube, api_key: event.target.value })
            }
          />
        </label>

        <label className="field">
          <span>Videos per channel per run</span>
          <input
            min={1}
            type="number"
            value={settings.youtube.max_videos_per_channel}
            onChange={(event) =>
              updateField('youtube', {
                ...settings.youtube,
                max_videos_per_channel: Number(event.target.value || 1),
              })
            }
          />
        </label>

        <label className="field">
          <span>Lookback window in hours</span>
          <input
            min={1}
            type="number"
            value={settings.youtube.lookback_hours}
            onChange={(event) =>
              updateField('youtube', {
                ...settings.youtube,
                lookback_hours: Number(event.target.value || 1),
              })
            }
          />
        </label>

        <label className="field">
          <span>Agent backend</span>
          <select
            value={settings.agent.backend}
            onChange={(event) =>
              updateField('agent', { ...settings.agent, backend: event.target.value })
            }
          >
            <option value="codex">Codex</option>
            <option value="claude-code">Claude Code</option>
            <option value="cursor">Cursor</option>
            <option value="copilot">GitHub Copilot</option>
          </select>
        </label>

        <label className="field">
          <span>Research timeout in seconds</span>
          <input
            min={30}
            step={30}
            type="number"
            value={settings.agent.research_timeout_seconds}
            onChange={(event) =>
              updateField('agent', {
                ...settings.agent,
                research_timeout_seconds: Number(event.target.value || 30),
              })
            }
          />
        </label>

        <div className="settings-block">
          <div className="settings-intro">
            Add the YouTube channels you want to scrape each morning. Use the channel ID from YouTube and a readable display name for the briefing.
          </div>
          <div className="field-row">
            <label className="field">
              <span>Channel ID</span>
              <input
                value={channelDraft.id}
                onChange={(event) => setChannelDraft((current) => ({ ...current, id: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Channel name</span>
              <input
                value={channelDraft.name}
                onChange={(event) =>
                  setChannelDraft((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
          </div>
          <label className="field">
            <span>Focus tags (comma separated)</span>
            <input
              value={channelDraft.focus}
              onChange={(event) => setChannelDraft((current) => ({ ...current, focus: event.target.value }))}
            />
          </label>
          <button className="editorial-button" onClick={addChannel} type="button">
            Add channel
          </button>
          <ul className="channel-list">
            {settings.youtube.channels.map((channel) => (
              <li className="channel-list__item" key={`${channel.id}-${channel.name}`}>
                <div>
                  <strong>{channel.name}</strong> · {channel.id}
                  {channel.focus.length > 0 ? (
                    <div className="channel-list__meta">{channel.focus.join(', ')}</div>
                  ) : null}
                </div>
                <button className="claim-inline__action" onClick={() => removeChannel(channel.id)} type="button">
                  remove
                </button>
              </li>
            ))}
          </ul>
        </div>

        <button className="editorial-button" onClick={save} type="button">
          Save settings
        </button>
        {note ? <div className="form-note">{note}</div> : null}
      </div>
    </section>
  )
}
