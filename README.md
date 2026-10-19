# CampusPulse AI

Автономный агент для студента: дедлайны, события кампуса и места для учёбы.
Стек: Gemini 2.5 Flash (Vertex AI), custom MCP server на FastMCP,
Vertex AI Agent Engine, Streamlit.

## Что внутри

- campuspulse/mcp_server.py — MCP-сервер с четырьмя инструментами:
  list_courses, get_deadlines, search_events, find_study_spot.
- campuspulse/agent.py — reasoning loop на Gemini с function calling.
  Агент сам поднимает MCP-сервер по stdio, собирает трейс и источники.
- app.py — Streamlit-чат с раскрывающимся reasoning loop.
- deploy.py — сборка Reasoning Engine и деплой в Agent Engine.
- campuspulse/data — демо-данные. Относительные оффсеты дат,
  чтобы демо оставалось актуальным.
- docs/test_scenarios.md — пять тестовых сценариев.
- docs/pitch.md — каркас презентации на 5–7 минут.

## Архитектура

Пользователь -> Streamlit -> CampusPulseAgent -> Gemini 2.5 Flash
                                      -> MCP stdio -> 4 tools -> demo data
Деплой: CampusPulseAgent -> ReasoningEngine -> Agent Engine endpoint

Факты о кампусе приходят только из MCP-инструментов. Модель не должна
утверждать «открыто сейчас» без поля open_now. В ответе есть source URI,
в UI — трейс вызовов и сырые результаты.

## Локальный запуск

1. Python 3.11+.
2. Создать окружение и поставить зависимости:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
3. Авторизоваться в GCP:
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
4. Задать переменные:
   $env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
   $env:GOOGLE_CLOUD_LOCATION="us-central1"
5. Запустить UI:
   streamlit run app.py

Для локальной проверки без GCP можно задать GEMINI_API_KEY.
Тогда агент пойдёт через Gemini API, а не через Vertex.

## Деплой в Vertex AI Agent Engine

1. Включить API:
   gcloud services enable aiplatform.googleapis.com storage.googleapis.com
2. Создать staging bucket:
   gcloud storage buckets create gs://YOUR_BUCKET --location=us-central1
3. Задать переменные:
   $env:STAGING_BUCKET="gs://YOUR_BUCKET"
4. Запустить:
   python deploy.py
5. Скрипт выведет AGENT_ENGINE_RESOURCE. Подставить его в окружение UI,
   чтобы Streamlit ходил в удалённый агент, а не в локальный.

Сервисному аккаунту Agent Engine нужны права на Vertex AI
(например, roles/aiplatform.user) и доступ к модели Gemini.

## MCP

MCP-сервер запускается агентом как subprocess по stdio.
Отдельно его можно открыть через MCP Inspector:
   npx @modelcontextprotocol/inspector python -m campuspulse.mcp_server

Для продакшена stdio-транспорт стоит заменить на streamable HTTP
и вынести сервер в Cloud Run. Тогда один MCP-сервер сможет
обслуживать несколько агентов и версий.

## Данные

Сейчас в JSON лежит синтетический демо-кампус. Для реального пилота:
- заменить courses.json на выгрузку из LMS;
- заменить events.json на API студенческого офиса или календарь;
- заменить locations.json на данные кампус-сервиса;
- для дедлайнов можно использовать абсолютное поле due вместо
  due_offset_days; оба варианта поддерживаются.

## Приватность и этика

- Точные координаты пользователя не собираются и не хранятся.
  Пользователь сам пишет контекст в чат.
- История и трейс живут только в сессии Streamlit. Базы нет.
- Все факты о кампусе помечены source URI.
- open_now означает «по опубликованным часам», а не «по факту».
  В туле есть отдельная пометка про отсутствие live occupancy.
- Сгенерированные советы помечаются как идея, а не как факт.
- Для продакшена: TTL логов, минимизация PII, согласие пользователя,
  аудит источников и ручной fallback для спорных мест.

## Ограничения

- Демо-данные синтетические, не привязаны к реальному кампусу.
- Нет live-загруженности, погоды и пробок.
- Agent Engine и Reasoning Engine — preview-контур, возможны
  изменения API и квоты.
- Модель всё ещё может ошибаться; промпт и источники снижают риск,
  но не убирают его полностью.
- В демо нет авторизации и rate limiting.

## Быстрая проверка сценариев

1. «Что у меня горит на этой неделе?»
2. «Нужно тихое место с розеткой и кофе до вечера.»
3. «Куда сходить по AI на этой неделе?»
4. «Успею ли подготовить Raft и CNN? Составь план.»
5. «Где ближайшая аптека?» — агент должен честно сказать,
   что таких данных в системе нет, и не выдумывать место.
