import { useState } from 'react'
import './App.css'

const AVATAR_OPTIONS = [
  { key: 'knight-1', label: 'Knight I' },
  { key: 'knight-2', label: 'Knight II' },
  { key: 'knight-3', label: 'Knight III' },
  { key: 'knight-4', label: 'Knight IV' },
]

const emptyRegister = {
  username: '',
  email: '',
  nickname: '',
  password: '',
  password_confirm: '',
}

const emptyLogin = {
  username: '',
  password: '',
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {}),
    },
  })

  const text = await response.text()
  const payload = text ? JSON.parse(text) : {}

  if (!response.ok) {
    const error = new Error(payload?.errors ? formatErrors(payload.errors) : 'Request failed')
    error.payload = payload
    error.status = response.status
    throw error
  }

  return payload
}

function formatErrors(errors) {
  if (!errors) return 'Request failed.'

  const firstError = Object.values(errors).flat()[0]
  return firstError || 'Request failed.'
}

function apiErrorsOrDefault(error, fallback = 'Request failed.') {
  if (error?.payload?.errors) {
    return error.payload.errors
  }

  return { non_field_errors: [error?.message || fallback] }
}

async function getCsrfToken() {
  const existing = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('csrftoken='))

  if (existing) {
    return existing.split('=')[1]
  }

  await requestJson('/api/auth/csrf/', { method: 'GET' })

  const token = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('csrftoken='))

  return token ? token.split('=')[1] : ''
}

async function withCsrf(url, options = {}) {
  const csrfToken = await getCsrfToken()
  return requestJson(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
      ...(options.headers || {}),
    },
  })
}

function App() {
  const [mode, setMode] = useState('login')
  const [user, setUser] = useState(null)
  const [registerForm, setRegisterForm] = useState(emptyRegister)
  const [loginForm, setLoginForm] = useState(emptyLogin)
  const [profileForm, setProfileForm] = useState({ nickname: '', avatar_key: 'knight-1' })
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [errors, setErrors] = useState({})

  const onRegisterChange = (event) => {
    setRegisterForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }))
  }

  const onLoginChange = (event) => {
    setLoginForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }))
  }

  const onProfileChange = (event) => {
    setProfileForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }))
  }

  const handleRegister = async (event) => {
    event.preventDefault()
    setLoading(true)
    setErrors({})
    setStatus('')

    if (!registerForm.username || !registerForm.email || !registerForm.nickname || !registerForm.password || !registerForm.password_confirm) {
      setErrors({
        non_field_errors: ['Please fill in all registration fields.'],
      })
      setStatus('Please fill in all registration fields.')
      setLoading(false)
      return
    }

    if (registerForm.password !== registerForm.password_confirm) {
      setErrors({
        password_confirm: ['Passwords do not match.'],
      })
      setStatus('Passwords do not match.')
      setLoading(false)
      return
    }

    try {
      const created = await withCsrf('/api/auth/register/', {
        method: 'POST',
        body: JSON.stringify(registerForm),
      })

      const loggedIn = await withCsrf('/api/auth/login/', {
        method: 'POST',
        body: JSON.stringify({
          username: registerForm.username,
          password: registerForm.password,
        }),
      })

      setUser(loggedIn)
      setProfileForm({
        nickname: loggedIn.profile.nickname,
        avatar_key: loggedIn.profile.avatar_key,
      })
      setRegisterForm(emptyRegister)
      setMode('profile')
      setStatus('Registration successful. Welcome to the arena!')
      console.log('Registered and authenticated:', created)
    } catch (error) {
      const nextErrors = apiErrorsOrDefault(error)
      setErrors(nextErrors)
      setStatus(formatErrors(nextErrors))
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async (event) => {
    event.preventDefault()
    setLoading(true)
    setErrors({})
    setStatus('')

    if (!loginForm.username || !loginForm.password) {
      setErrors({
        non_field_errors: ['Please enter both username and password.'],
      })
      setStatus('Please enter both username and password.')
      setLoading(false)
      return
    }

    try {
      const payload = await withCsrf('/api/auth/login/', {
        method: 'POST',
        body: JSON.stringify(loginForm),
      })

      setUser(payload)
      setProfileForm({
        nickname: payload.profile.nickname,
        avatar_key: payload.profile.avatar_key,
      })
      setLoginForm(emptyLogin)
      setMode('profile')
      setStatus('Login successful.')
    } catch (error) {
      const nextErrors = apiErrorsOrDefault(error)
      setErrors(nextErrors)
      setStatus(formatErrors(nextErrors))
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    setLoading(true)
    setErrors({})
    setStatus('')

    try {
      await withCsrf('/api/auth/logout/', {
        method: 'POST',
      })
      setUser(null)
      setMode('login')
      setStatus('You have been logged out.')
    } catch (error) {
      setStatus(error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleProfileSave = async (event) => {
    event.preventDefault()
    setLoading(true)
    setErrors({})
    setStatus('')

    try {
      const payload = await withCsrf('/api/auth/me/', {
        method: 'PATCH',
        body: JSON.stringify({
          nickname: profileForm.nickname,
          avatar_key: profileForm.avatar_key,
        }),
      })

      setUser(payload)
      setProfileForm({
        nickname: payload.profile.nickname,
        avatar_key: payload.profile.avatar_key,
      })
      setStatus('Profile updated successfully.')
    } catch (error) {
      const nextErrors = apiErrorsOrDefault(error)
      setErrors(nextErrors)
      setStatus(formatErrors(nextErrors))
    } finally {
      setLoading(false)
    }
  }

  const renderInlineErrors = (field) => {
    const fieldErrors = errors[field]
    if (!fieldErrors) return null
    return fieldErrors.map((message) => (
      <small key={message} className="field-error">
        {message}
      </small>
    ))
  }

  return (
    <div className="app-shell">
      <div className="glow glow-1" />
      <div className="glow glow-2" />

      <main className="auth-layout">
        <section className="brand-panel">
          <div className="brand-badge">Conquiztador</div>
          <h1>Power up your next quiz battle.</h1>
          <p>
            Join the arena, prove your trivia mastery, and keep your player profile ready for the next match.
          </p>

          <div className="feature-list">
            <div>
              <span className="dot" />
              Smart session auth
            </div>
            <div>
              <span className="dot" />
              Secure profile management
            </div>
            <div>
              <span className="dot" />
              Fast multiplayer-ready flow
            </div>
          </div>
        </section>

        <section className="card-panel">
          {!user ? (
            <>
              <div className="tab-row">
                <button
                  type="button"
                  className={mode === 'login' ? 'tab active' : 'tab'}
                  onClick={() => setMode('login')}
                >
                  Login
                </button>
                <button
                  type="button"
                  className={mode === 'register' ? 'tab active' : 'tab'}
                  onClick={() => setMode('register')}
                >
                  Register
                </button>
              </div>

              {mode === 'login' ? (
                <form className="auth-form" onSubmit={handleLogin}>
                  <h2>Welcome back</h2>
                  <label>
                    <span>Username</span>
                    <input
                      name="username"
                      value={loginForm.username}
                      onChange={onLoginChange}
                      placeholder="player_one"
                    />
                  </label>

                  <label>
                    <span>Password</span>
                    <input
                      type="password"
                      name="password"
                      value={loginForm.password}
                      onChange={onLoginChange}
                      placeholder="••••••••"
                    />
                  </label>

                  {renderInlineErrors('non_field_errors')}

                  <button type="submit" className="primary-btn" disabled={loading}>
                    {loading ? 'Signing in...' : 'Login'}
                  </button>
                </form>
              ) : (
                <form className="auth-form" onSubmit={handleRegister}>
                  <h2>Create player account</h2>

                  <div className="two-col">
                    <label>
                      <span>Username</span>
                      <input
                        name="username"
                        value={registerForm.username}
                        onChange={onRegisterChange}
                        placeholder="player_one"
                      />
                    </label>

                    <label>
                      <span>Email</span>
                      <input
                        type="email"
                        name="email"
                        value={registerForm.email}
                        onChange={onRegisterChange}
                        placeholder="player@example.com"
                      />
                    </label>
                  </div>

                  <label>
                    <span>Nickname</span>
                    <input
                      name="nickname"
                      value={registerForm.nickname}
                      onChange={onRegisterChange}
                      placeholder="MountainKnight"
                    />
                  </label>

                  <div className="two-col">
                    <label>
                      <span>Password</span>
                      <input
                        type="password"
                        name="password"
                        value={registerForm.password}
                        onChange={onRegisterChange}
                        placeholder="••••••••"
                      />
                    </label>

                    <label>
                      <span>Confirm</span>
                      <input
                        type="password"
                        name="password_confirm"
                        value={registerForm.password_confirm}
                        onChange={onRegisterChange}
                        placeholder="••••••••"
                      />
                    </label>
                  </div>

                  {renderInlineErrors('username')}
                  {renderInlineErrors('email')}
                  {renderInlineErrors('nickname')}
                  {renderInlineErrors('password_confirm')}
                  {renderInlineErrors('non_field_errors')}

                  <button type="submit" className="primary-btn" disabled={loading}>
                    {loading ? 'Creating account...' : 'Register'}
                  </button>
                </form>
              )}
            </>
          ) : (
            <form className="profile-form" onSubmit={handleProfileSave}>
              <div className="profile-header">
                <div>
                  <span className="eyebrow">Player profile</span>
                  <h2>{user.username}</h2>
                </div>
                <button type="button" className="ghost-btn" onClick={handleLogout}>
                  Logout
                </button>
              </div>

              <div className="profile-summary">
                <div className="avatar-circle">{user.profile.nickname.slice(0, 2).toUpperCase()}</div>
                <div>
                  <strong>{user.profile.nickname}</strong>
                  <small>{user.email}</small>
                </div>
              </div>

              <label>
                <span>Nickname</span>
                <input
                  name="nickname"
                  value={profileForm.nickname}
                  onChange={onProfileChange}
                  placeholder="Your nickname"
                />
              </label>

              <div className="avatar-grid">
                {AVATAR_OPTIONS.map((avatar) => (
                  <button
                    key={avatar.key}
                    type="button"
                    className={profileForm.avatar_key === avatar.key ? 'avatar-option selected' : 'avatar-option'}
                    onClick={() => setProfileForm((current) => ({ ...current, avatar_key: avatar.key }))}
                  >
                    <span className="avatar-tile">{avatar.label}</span>
                  </button>
                ))}
              </div>

              {renderInlineErrors('nickname')}
              {renderInlineErrors('avatar_key')}
              {renderInlineErrors('non_field_errors')}

              <button type="submit" className="primary-btn" disabled={loading}>
                {loading ? 'Saving...' : 'Save profile'}
              </button>
            </form>
          )}

          {status ? <div className="status-banner">{status}</div> : null}
        </section>
      </main>
    </div>
  )
}

export default App
