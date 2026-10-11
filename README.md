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
