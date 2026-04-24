import { useEffect, useState } from 'react'

import { getSettings, putSettings, resolveChannel, testGoogleSearch } from '../lib/api'
import type { AppSettings, GoogleSearchResult, ResolvedChannel } from '../types'

const EMPTY_SETTINGS: AppSettings = {
  youtube: {
    api_key: '',
    channels: [],
    max_videos_per_channel: 5,
    lookback_hours: 24,
  },
  agent: {
    backend: 'codex',
    model: '',
    capital_iq_model: '',
    analysis_model: '',
    research_model: '',
    editorial_model: '',
    translation_model: '',
    max_concurrent_research: 2,
    research_timeout_seconds: 600,
  },
  google_search: {
    api_key: '',
    engine_id: '',
  },
  capital_iq: {
    username: '',
    password: '',
  },
  watchlist: {
    stocks: [],
    valuation_refresh_days: 7,
  },
  transcription: {
    backend: 'captions_then_local',
    model: 'large-v3',
    device: 'auto',
    compute_type: 'auto',
    language: '',
    caption_languages: ['en', 'de'],
    vad_filter: true,
    beam_size: 5,
    temperature: 0,
    condition_on_previous_text: true,
    keep_audio: false,
    max_duration_minutes: 90,
    output_formats: ['txt', 'json', 'vtt'],
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
  const [watchlistDraft, setWatchlistDraft] = useState({ ticker: '', name: '', notes: '' })
  const [note, setNote] = useState<string | null>(null)
  const [channelCheck, setChannelCheck] = useState<ResolvedChannel | null>(null)
  const [channelCheckError, setChannelCheckError] = useState<string | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [showCapitalIqPassword, setShowCapitalIqPassword] = useState(false)
  const [searchCheck, setSearchCheck] = useState<GoogleSearchResult[]>([])
  const [searchCheckError, setSearchCheckError] = useState<string | null>(null)

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

  function addWatchlistStock() {
    const ticker = watchlistDraft.ticker.trim().toUpperCase()
    if (!ticker) {
      setNote('Add a ticker before saving a watchlist name.')
      return
    }
    if (settings.watchlist.stocks.some((stock) => stock.ticker.toUpperCase() === ticker)) {
      setNote(`${ticker} is already on your watchlist.`)
      return
    }
    updateField('watchlist', {
      ...settings.watchlist,
      stocks: settings.watchlist.stocks.concat({
        ticker,
        name: watchlistDraft.name.trim(),
        notes: watchlistDraft.notes.trim(),
      }),
    })
    setWatchlistDraft({ ticker: '', name: '', notes: '' })
    setNote(null)
  }

  function removeWatchlistStock(ticker: string) {
    updateField('watchlist', {
      ...settings.watchlist,
      stocks: settings.watchlist.stocks.filter((stock) => stock.ticker !== ticker),
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

  async function checkGoogleSearchConfig() {
    setSearchCheck([])
    setSearchCheckError(null)
    if (!settings.google_search.engine_id.trim()) {
      setSearchCheckError('Add a Programmable Search Engine ID first.')
      return
    }
    try {
      const payload = await testGoogleSearch(
        settings.google_search.api_key,
        settings.youtube.api_key,
        settings.google_search.engine_id,
      )
      setSearchCheck(payload.results)
      setNote('Google search credentials are working.')
    } catch (error) {
      setSearchCheckError(error instanceof Error ? error.message : 'Could not verify Google search.')
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
          <div className="field-row">
            <label className="field">
              <span>Global Claude fallback</span>
              <input
                placeholder="opus"
                value={settings.agent.model}
                onChange={(event) =>
                  updateField('agent', { ...settings.agent, model: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Legacy Capital IQ fallback</span>
              <input
                placeholder="haiku"
                value={settings.agent.capital_iq_model}
                onChange={(event) =>
                  updateField('agent', { ...settings.agent, capital_iq_model: event.target.value })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Analysis Claude model</span>
              <input
                placeholder="sonnet"
                value={settings.agent.analysis_model}
                onChange={(event) =>
                  updateField('agent', { ...settings.agent, analysis_model: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Research Claude model</span>
              <input
                placeholder="haiku"
                value={settings.agent.research_model}
                onChange={(event) =>
                  updateField('agent', { ...settings.agent, research_model: event.target.value })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Editorial Claude model</span>
              <input
                placeholder="opus"
                value={settings.agent.editorial_model}
                onChange={(event) =>
                  updateField('agent', { ...settings.agent, editorial_model: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Translation Claude model</span>
              <input
                placeholder="haiku"
                value={settings.agent.translation_model}
                onChange={(event) =>
                  updateField('agent', { ...settings.agent, translation_model: event.target.value })
                }
              />
            </label>
          </div>
          <div className="form-note">
            These model overrides are used only when the backend is `Claude Code`. Stage-specific fields fall back to
            the global model, and Capital IQ-style research also honors the legacy Capital IQ fallback when the
            research field is blank.
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
            <div className="section-label">Transcription</div>
            <h2 className="settings-section__title">Local Whisper pipeline</h2>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Transcript strategy</span>
              <select
                value={settings.transcription.backend}
                onChange={(event) =>
                  updateField('transcription', { ...settings.transcription, backend: event.target.value as AppSettings['transcription']['backend'] })
                }
              >
                <option value="captions_then_local">Captions first, then local Whisper</option>
                <option value="local_only">Always use local Whisper</option>
                <option value="captions_only">Only use captions</option>
              </select>
            </label>
            <label className="field">
              <span>Whisper model</span>
              <input
                value={settings.transcription.model}
                onChange={(event) =>
                  updateField('transcription', { ...settings.transcription, model: event.target.value })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Device</span>
              <input
                value={settings.transcription.device}
                onChange={(event) =>
                  updateField('transcription', { ...settings.transcription, device: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Compute type</span>
              <input
                value={settings.transcription.compute_type}
                onChange={(event) =>
                  updateField('transcription', { ...settings.transcription, compute_type: event.target.value })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Caption languages</span>
              <input
                value={settings.transcription.caption_languages.join(', ')}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    caption_languages: event.target.value
                      .split(',')
                      .map((value) => value.trim())
                      .filter(Boolean),
                  })
                }
              />
            </label>
            <label className="field">
              <span>Forced language override</span>
              <input
                placeholder="Leave blank for auto-detect"
                value={settings.transcription.language}
                onChange={(event) =>
                  updateField('transcription', { ...settings.transcription, language: event.target.value })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Beam size</span>
              <input
                min={1}
                type="number"
                value={settings.transcription.beam_size}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    beam_size: Number(event.target.value || 1),
                  })
                }
              />
            </label>
            <label className="field">
              <span>Max duration in minutes</span>
              <input
                min={1}
                type="number"
                value={settings.transcription.max_duration_minutes}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    max_duration_minutes: Number(event.target.value || 1),
                  })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Temperature</span>
              <input
                min={0}
                step={0.1}
                type="number"
                value={settings.transcription.temperature}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    temperature: Number(event.target.value || 0),
                  })
                }
              />
            </label>
            <label className="field">
              <span>Artifacts</span>
              <input
                value={settings.transcription.output_formats.join(', ')}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    output_formats: event.target.value
                      .split(',')
                      .map((value) => value.trim())
                      .filter((value): value is 'txt' | 'json' | 'vtt' => ['txt', 'json', 'vtt'].includes(value)),
                  })
                }
              />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Use VAD filtering</span>
              <select
                value={settings.transcription.vad_filter ? 'true' : 'false'}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    vad_filter: event.target.value === 'true',
                  })
                }
              >
                <option value="true">Enabled</option>
                <option value="false">Disabled</option>
              </select>
            </label>
            <label className="field">
              <span>Keep downloaded audio</span>
              <select
                value={settings.transcription.keep_audio ? 'true' : 'false'}
                onChange={(event) =>
                  updateField('transcription', {
                    ...settings.transcription,
                    keep_audio: event.target.value === 'true',
                  })
                }
              >
                <option value="false">Delete after transcription</option>
                <option value="true">Keep cached audio</option>
              </select>
            </label>
          </div>
          <label className="field">
            <span>Condition on previous text</span>
            <select
              value={settings.transcription.condition_on_previous_text ? 'true' : 'false'}
              onChange={(event) =>
                updateField('transcription', {
                  ...settings.transcription,
                  condition_on_previous_text: event.target.value === 'true',
                })
              }
            >
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
            <div className="form-note">
              These settings control the local `faster-whisper` fallback used when captions are unavailable or disabled.
            </div>
          </label>
        </section>

        <section className="settings-section">
          <div className="settings-section__header">
            <div className="section-label">Research</div>
            <h2 className="settings-section__title">Google web search</h2>
          </div>
          <label className="field">
            <span>Google Search API key</span>
            <input
              value={settings.google_search.api_key}
              onChange={(event) =>
                updateField('google_search', { ...settings.google_search, api_key: event.target.value })
              }
            />
            <div className="form-note">
              Optional. Leave blank to reuse the Google key from the YouTube section.
            </div>
          </label>
          <label className="field">
            <span>Programmable Search Engine ID</span>
            <input
              value={settings.google_search.engine_id}
              onChange={(event) =>
                updateField('google_search', { ...settings.google_search, engine_id: event.target.value })
              }
            />
          </label>
          <div className="settings-actions">
            <button className="editorial-button editorial-button--boxed" onClick={checkGoogleSearchConfig} type="button">
              Check Google search
            </button>
          </div>
          {searchCheckError ? <div className="form-note form-note--error">{searchCheckError}</div> : null}
          {searchCheck.length > 0 ? (
            <ul className="channel-list">
              {searchCheck.map((item) => (
                <li className="channel-list__item" key={item.link}>
                  <div>
                    <strong>{item.title}</strong>
                    <div className="channel-list__meta">{item.snippet}</div>
                    <div className="channel-list__meta">
                      <a href={item.link} rel="noreferrer" target="_blank">
                        {item.link}
                      </a>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="settings-section">
          <div className="settings-section__header">
            <div className="section-label">Research</div>
            <h2 className="settings-section__title">Capital IQ access</h2>
          </div>
          <div className="field-row">
            <label className="field">
              <span>Capital IQ username</span>
              <input
                autoComplete="username"
                value={settings.capital_iq.username}
                onChange={(event) =>
                  updateField('capital_iq', { ...settings.capital_iq, username: event.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Capital IQ password</span>
              <div className="field-inline">
                <input
                  autoComplete="current-password"
                  type={showCapitalIqPassword ? 'text' : 'password'}
                  value={settings.capital_iq.password}
                  onChange={(event) =>
                    updateField('capital_iq', { ...settings.capital_iq, password: event.target.value })
                  }
                />
                <button
                  className="editorial-button"
                  onClick={() => setShowCapitalIqPassword((current) => !current)}
                  type="button"
                >
                  {showCapitalIqPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </label>
          </div>
          <div className="form-note">
            Used by the Capital IQ browser skill for authenticated research. Stored locally in `config/settings.json`.
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-section__header">
            <div className="section-label">Research</div>
            <h2 className="settings-section__title">Stock watchlist</h2>
          </div>
          <div className="settings-intro">
            Add stocks you want the briefing agent to prioritize. When those names show up in coverage, the
            briefing will give them extra weight and the Capital IQ sub-agent will refresh valuation context on a
            recurring cadence.
          </div>
          <div className="field-row">
            <label className="field">
              <span>Ticker</span>
              <input
                placeholder="NVDA"
                value={watchlistDraft.ticker}
                onChange={(event) =>
                  setWatchlistDraft((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))
                }
              />
            </label>
            <label className="field">
              <span>Company name</span>
              <input
                placeholder="NVIDIA"
                value={watchlistDraft.name}
                onChange={(event) => setWatchlistDraft((current) => ({ ...current, name: event.target.value }))}
              />
            </label>
          </div>
          <label className="field">
            <span>Why it matters</span>
            <input
              placeholder="AI capex leader, data-center demand, valuation risk"
              value={watchlistDraft.notes}
              onChange={(event) => setWatchlistDraft((current) => ({ ...current, notes: event.target.value }))}
            />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Refresh valuation every N days</span>
              <input
                min={1}
                type="number"
                value={settings.watchlist.valuation_refresh_days}
                onChange={(event) =>
                  updateField('watchlist', {
                    ...settings.watchlist,
                    valuation_refresh_days: Number(event.target.value || 1),
                  })
                }
              />
            </label>
          </div>
          <div className="settings-actions">
            <button className="editorial-button editorial-button--boxed" onClick={addWatchlistStock} type="button">
              Add stock
            </button>
          </div>
          {settings.watchlist.stocks.length === 0 ? (
            <p className="empty-state">No watchlist stocks configured yet.</p>
          ) : (
            <ul className="channel-list">
              {settings.watchlist.stocks.map((stock) => (
                <li className="channel-list__item" key={stock.ticker}>
                  <div>
                    <strong>{stock.ticker}</strong>
                    {stock.name ? ` · ${stock.name}` : null}
                    {stock.notes ? <div className="channel-list__meta">{stock.notes}</div> : null}
                  </div>
                  <button
                    className="claim-inline__action"
                    onClick={() => removeWatchlistStock(stock.ticker)}
                    type="button"
                  >
                    remove
                  </button>
                </li>
              ))}
            </ul>
          )}
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
