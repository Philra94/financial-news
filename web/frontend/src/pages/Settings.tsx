import { useEffect, useState } from 'react'

import { getSettings, putSettings, resolveChannel } from '../lib/api'
import type { AppSettings, ResolvedChannel } from '../types'

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
  const [channelDraft, setChannelDraft] = useState({ url: '', focus: '' })
  const [note, setNote] = useState<string | null>(null)
  const [channelCheck, setChannelCheck] = useState<ResolvedChannel | null>(null)
  const [channelCheckError, setChannelCheckError] = useState<string | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)

  useEffect(() => {
    getSettings().then(setSettings)
  }, [])

  function updateField<T extends keyof AppSettings>(key: T, value: AppSettings[T]) {
    setSettings((current) => ({ ...current, [key]: value }))
  }

  function canonicalChannelUrl(channelId: string) {
    return `https://www.youtube.com/channel/${channelId}`
  }

  async function addChannel() {
    let resolvedChannel = channelCheck
    if (!settings.youtube.api_key) {
      setChannelCheckError('Add a YouTube Data API key first.')
      return
    }
    if (!channelDraft.url.trim()) {
      setChannelCheckError('Paste a YouTube channel URL first.')
      return
    }
    if (!resolvedChannel || resolvedChannel.source_input !== channelDraft.url.trim()) {
      try {
        resolvedChannel = await resolveChannel(settings.youtube.api_key, channelDraft.url.trim())
        setChannelCheck(resolvedChannel)
      } catch (error) {
        setChannelCheckError(error instanceof Error ? error.message : 'Could not resolve channel.')
        return
      }
    }
    if (settings.youtube.channels.some((channel) => channel.id === resolvedChannel.id)) {
      setNote(`${resolvedChannel.name} is already in your channel list.`)
      setChannelCheckError(null)
      return
    }
    updateField('youtube', {
      ...settings.youtube,
      channels: settings.youtube.channels.concat({
        id: resolvedChannel.id,
        name: resolvedChannel.name,
        focus: channelDraft.focus
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
        source_input: resolvedChannel.source_input,
      }),
    })
    setChannelDraft({ url: '', focus: '' })
    setChannelCheck(null)
    setChannelCheckError(null)
  }

  function removeChannel(channelId: string) {
    updateField('youtube', {
      ...settings.youtube,
      channels: settings.youtube.channels.filter((channel) => channel.id !== channelId),
    })
  }

  async function save() {
    try {
      const saved = await putSettings(settings)
      setSettings(saved)
      setNote('Settings saved.')
    } catch (error) {
      setNote(error instanceof Error ? error.message : 'Unable to save settings.')
    }
  }

  async function checkChannel() {
    setChannelCheck(null)
    setChannelCheckError(null)
    if (!settings.youtube.api_key) {
      setChannelCheckError('Add a YouTube Data API key first.')
      return
    }
    if (!channelDraft.url.trim()) {
      setChannelCheckError('Paste a YouTube channel URL first.')
      return
    }
    try {
      const resolved = await resolveChannel(settings.youtube.api_key, channelDraft.url.trim())
      setChannelCheck(resolved)
    } catch (error) {
      setChannelCheckError(error instanceof Error ? error.message : 'Could not resolve channel.')
    }
  }

  return (
    <section>
      <div className="section-label">Settings</div>
      <h1 className="briefing-title">Configuration</h1>
      <p className="page-lead">
        Manage the local inputs that power the morning edition. Channel details are resolved from the YouTube API
        before they are saved.
      </p>

      <div className="settings-form">
        <section className="settings-section">
          <div className="settings-section__header">
            <div className="section-label">Publication</div>
            <h2 className="settings-section__title">Edition settings</h2>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Site title</span>
              <input
                value={settings.site.title}
                onChange={(event) => updateField('site', { ...settings.site, title: event.target.value })}
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
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-section__header">
            <div className="section-label">Pipeline</div>
            <h2 className="settings-section__title">Data collection</h2>
          </div>
          <label className="field">
            <span>YouTube Data API key</span>
            <div className="field-inline">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={settings.youtube.api_key}
                onChange={(event) =>
                  updateField('youtube', { ...settings.youtube, api_key: event.target.value })
                }
              />
              <button className="editorial-button" onClick={() => setShowApiKey((current) => !current)} type="button">
                {showApiKey ? 'Hide' : 'Show'}
              </button>
            </div>
            <div className="form-note">Stored locally in `config/settings.json` on this machine.</div>
          </label>
          <div className="field-row">
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
          </div>
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
        </section>

        <section className="settings-section">
          <div className="settings-section__header">
            <div className="section-label">Channels</div>
            <h2 className="settings-section__title">Scrape list</h2>
          </div>
          <div className="settings-intro">
            Add the YouTube channels you want to scrape each morning by pasting an exact YouTube channel URL.
            Supported formats are `https://www.youtube.com/@handle` and `https://www.youtube.com/channel/UC...`.
            The app resolves the real channel ID and display name from the YouTube API before saving.
          </div>
          <div className="field-row">
            <label className="field">
              <span>YouTube channel URL</span>
              <input
                placeholder="https://www.youtube.com/@kochwallstreet"
                value={channelDraft.url}
                onChange={(event) => {
                  setChannelDraft((current) => ({ ...current, url: event.target.value }))
                  setChannelCheck(null)
                  setChannelCheckError(null)
                  setNote(null)
                }}
              />
            </label>
            <label className="field">
              <span>Focus tags (comma separated)</span>
              <input
                value={channelDraft.focus}
                onChange={(event) => setChannelDraft((current) => ({ ...current, focus: event.target.value }))}
              />
            </label>
          </div>
          <div className="settings-actions">
            <button className="editorial-button editorial-button--boxed" onClick={checkChannel} type="button">
              Check channel
            </button>
            <button className="editorial-button editorial-button--boxed" onClick={addChannel} type="button">
              Add channel
            </button>
          </div>
          {channelCheck ? (
            <div className="channel-check channel-check--success">
              Exact match: <strong>{channelCheck.name}</strong> · {channelCheck.id} ·{' '}
              <a href={channelCheck.url} rel="noreferrer" target="_blank">
                canonical channel page
              </a>
            </div>
          ) : null}
          {channelCheckError ? <div className="form-note form-note--error">{channelCheckError}</div> : null}
          {settings.youtube.channels.length === 0 ? (
            <p className="empty-state">No channels configured yet.</p>
          ) : (
            <ul className="channel-list">
              {settings.youtube.channels.map((channel) => (
                <li className="channel-list__item" key={`${channel.id}-${channel.name}`}>
                  <div>
                    <strong>{channel.name}</strong> · {channel.id}
                    <div className="channel-list__meta">
                      <a href={canonicalChannelUrl(channel.id)} rel="noreferrer" target="_blank">
                        canonical channel URL
                      </a>
                    </div>
                    {channel.source_input ? (
                      <div className="channel-list__meta">added from {channel.source_input}</div>
                    ) : null}
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
          )}
        </section>

        <button className="editorial-button" onClick={save} type="button">
          Save settings
        </button>
        {note ? <div className="form-note">{note}</div> : null}
      </div>
    </section>
  )
}
