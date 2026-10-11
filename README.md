# Triviador

A clone of the board game Triviador built with Django (backend) and React (frontend). Players answer trivia questions to move armies across territories and capture capitals.

## Project Structure

- **backend/** - Django REST API with game logic, territories, players, and trivia questions
- **frontend/** - React SPA for the game interface

## Map: Bulgarian Territories

The game map consists of 18 Bulgarian territories connected by adjacent borders:

| Territory | Neighbors |
|-----------|-----------|
| Скали | Дунавия, Мадара, Житно поле |
| Дунавия | Скали, Мадара, Житно поле |
| Мадара | Скали, Дунавия, Калиакра, Житно поле |
| Калиакра | Мадара, Пеликания, Средец |
| Пеликания | Калиакра, Царево, Средец |
| Царево | Пеликания, Средец, Езера, Слънчево |
| Житно поле | Скали, Дунавия, Мадара, Балкания, Средец |
| Средец | Калиакра, Пеликания, Царево, Житно поле, Балкания, Езера, Чуден край |
| Балкания | Житно поле, Средец, Езера, Пирина, Розова долина |
| Езера | Царево, Средец, Балкания, Пирина, Чуден край |
| Пирина | Балкания, Езера, Розова долина, Каракачан |
| Розова долина | Балкания, Пирина, Каракачан, Кукери, Златен грозд |
| Чуден край | Средец, Езера, Кукери, Слънчево, Левента |
| Кукери | Розова долина, Чуден край, Левента, Каракачан, Слънчево, Златен грозд |
| Каракачан | Пирина, Розова долина, Кукери, Левента |
| Левента | Чуден край, Кукери, Каракачан, Слънчево |
| Слънчево | Царево, Чуден край, Левента, Кукери |
| Златен грозд | Розова долина, Кукери |

## Game Initialization (M05)

A `Game` starts in `waiting` status with no territories or capitals. Setup only happens when initialization is **explicitly invoked**; it is not automatic.

### How to initialize

Call `game.initialize()`. It delegates to the `GameInitializer` service (`backend/games/services/initializer.py`):

```python
game.initialize()  # selects the capitals randomly
```

The optional `random_selector` argument (`game.initialize(random_selector=...)`) exists only to make capital selection deterministic in tests; normal usage calls `game.initialize()` with no arguments.

### Preconditions

Initialization is rejected with a `ValidationError` unless all of the following hold:

- The game exists and has status `waiting`.
- The game has exactly three players.
- The game has no existing territory or capital records.
- The M04 map definition is valid (see [Map: Bulgarian Territories](#map-bulgarian-territories)).

A partially or fully initialized game is rejected, not automatically repaired.

### Initialization result

On success:

- All predefined territories are created, exactly matching the M04 map, with the same adjacency relationships.
- Every territory starts with score `0`.
- Three capitals are created, one per player, each with health `3`.
- Each capital territory is owned by its respective player; all other territories remain neutral (`owner = None`).
- The game status becomes `active`.

### Capital selection

The three capitals are selected randomly from all valid independent sets of size three, i.e. three **distinct, pairwise non-adjacent** territories. If the map contains no such set, initialization fails.

### Atomicity and errors

Initialization runs inside a single transaction (`@transaction.atomic`). It either succeeds completely or rolls back every change, leaving the database unchanged. Any failed precondition (wrong status, wrong player count, pre-existing territories or capitals, invalid map) raises a `ValidationError`. Repeated initialization attempts on an already-initialized game are rejected rather than repaired.

### Concurrency

`GameInitializer.initialize` acquires a row lock via `select_for_update()` on the game, so on databases with row-level locking (e.g. PostgreSQL) simultaneous initializations are serialized: the losing attempt waits, then re-checks the preconditions and fails cleanly.

The project is currently configured with **SQLite**, which does not support `SELECT ... FOR UPDATE`; Django silently ignores the lock (it is a no-op). SQLite instead serializes writes at the database level, so a concurrent second attempt either blocks until the first commits and then fails the precondition checks, or raises a "database is locked" error. Row-level locking is therefore not actually enforced under the current SQLite configuration.

### Scope

Initialization only creates territories, adjacencies, and capitals, and transitions the status. It is not triggered by `Game` creation or any signal, and it does not create players or rounds, nor implement any subsequent gameplay.
