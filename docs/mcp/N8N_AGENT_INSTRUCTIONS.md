# N8N Agent Instructions: Construction Estimator MCP Tools

## Обзор

Этот документ описывает как использовать 5 MCP инструментов для работы со строительными расценками в N8N workflows. MCP сервер предоставляет доступ к базе данных из 28,686 расценок и 294,883 ресурсов.

## Подключение к MCP Server

**Endpoint:** `http://host.docker.internal:8002/sse`
**Transport:** HTTP/SSE
**Health Check:** `http://host.docker.internal:8003/health`

## Доступные инструменты (Tools)

### 1. `natural_search` - Поиск расценок по описанию

**Назначение:** Полнотекстовый поиск расценок на русском языке

**Входные параметры:**
```json
{
  "query": "перегородки гипсокартон",
  "unit_type": "м2",          // опционально: фильтр по единице измерения
  "limit": 10                 // опционально: макс. кол-во результатов (по умолчанию 10, макс 100)
}
```

**Выходные данные:**
```json
{
  "success": true,
  "count": 5,
  "results": [
    {
      "rate_code": "ГЭСНп10-05-001-01",
      "rate_full_name": "Устройство перегородок из гипсокартонных листов...",
      "rate_short_name": "Перегородки ГКЛ однослойные",
      "unit_measure_full": "100 м2 перегородок",
      "cost_per_unit": 13832.02,
      "total_cost": 13832.02,
      "rank": 0.15
    }
  ]
}
```

**Когда использовать:**
- Пользователь описывает работу словами (не знает код расценки)
- Нужно найти несколько вариантов для сравнения
- Поиск по категории работ

**Пример N8N Node:**
```
HTTP Request Node
- Method: POST
- URL: http://host.docker.internal:8002/mcp/tool/natural_search
- Body:
  {
    "query": "{{ $json.user_query }}",
    "limit": 5
  }
```

---

### 2. `quick_calculate` - Быстрый расчет стоимости

**Назначение:** Универсальный калькулятор - принимает код расценки ИЛИ описание

**Входные параметры:**
```json
{
  "rate_identifier": "10-05-001-01",  // код расценки ИЛИ описание
  "quantity": 150.5                   // объем работ (обязательно > 0)
}
```

**Примеры rate_identifier:**
- Код расценки: `"10-05-001-01"`, `"ГЭСНп81-01-001"`
- Описание: `"перегородки гипсокартон"` (автоматически найдет лучшую расценку)

**Выходные данные:**
```json
{
  "success": true,
  "rate_info": {
    "rate_code": "ГЭСНп10-05-001-01",
    "rate_full_name": "Устройство перегородок...",
    "unit_type": "100 м2 перегородок"
  },
  "cost_per_unit": 13832.02,
  "calculated_total": 20800.23,
  "materials": 8500.50,
  "resources": 12299.73,
  "quantity": 150.5,
  "search_used": false
}
```

**Когда использовать:**
- Нужен быстрый расчет стоимости
- Пользователь может дать код или описание
- Не требуется детальная разбивка по ресурсам

**Пример N8N Workflow:**
```
1. Webhook (получить запрос пользователя)
2. HTTP Request:
   - URL: http://host.docker.internal:8002/mcp/tool/quick_calculate
   - Body: { "rate_identifier": "{{ $json.description }}", "quantity": {{ $json.volume }} }
3. Set Node (форматировать ответ)
4. Respond to Webhook
```

---

### 3. `show_rate_details` - Детальная разбивка расценки

**Назначение:** Получить полную детализацию по материалам, труду и технике

**Входные параметры:**
```json
{
  "rate_code": "10-05-001-01",
  "quantity": 150.0              // опционально, по умолчанию 1.0
}
```

**Выходные данные:**
```json
{
  "success": true,
  "rate_info": {
    "rate_code": "ГЭСНп10-05-001-01",
    "rate_full_name": "Устройство перегородок...",
    "unit_type": "100 м2 перегородок"
  },
  "total_cost": 20748.03,
  "cost_per_unit": 13832.02,
  "materials": 12759.60,
  "resources": 7988.43,
  "quantity": 150.0,
  "breakdown": [
    {
      "resource_code": "101-1529",
      "resource_name": "Листы гипсокартонные",
      "resource_type": "Material",
      "adjusted_quantity": 450.0,
      "unit": "м2",
      "unit_cost": 25.50,
      "adjusted_cost": 11475.00
    },
    {
      "resource_code": "101-0819",
      "resource_name": "Профили металлические",
      "resource_type": "Material",
      "adjusted_quantity": 225.0,
      "unit": "м.п.",
      "unit_cost": 5.71,
      "adjusted_cost": 1284.75
    }
    // ... больше ресурсов
  ]
}
```

**Когда использовать:**
- Нужна детальная смета с разбивкой по материалам
- Анализ структуры затрат
- Подготовка документации для заказчика

**Пример N8N Workflow с таблицей:**
```
1. HTTP Request (get details)
2. Split Out (разделить breakdown на отдельные элементы)
3. Google Sheets (записать каждый ресурс в строку таблицы)
```

---

### 4. `compare_variants` - Сравнение нескольких расценок

**Назначение:** Сравнить 2 или более расценок side-by-side

**Входные параметры:**
```json
{
  "rate_codes": ["10-05-001-01", "10-06-037-02", "11-01-015-01"],
  "quantity": 100.0
}
```

**Выходные данные:**
```json
{
  "success": true,
  "count": 3,
  "comparison": [
    {
      "rate_code": "10-05-001-01",
      "rate_full_name": "Устройство перегородок однослойных",
      "unit_type": "100 м2",
      "cost_per_unit": 13832.02,
      "total_for_quantity": 13832.02,
      "materials_for_quantity": 8506.40,
      "difference_from_cheapest": 0.00,
      "difference_percent": 0.00
    },
    {
      "rate_code": "10-06-037-02",
      "rate_full_name": "Устройство перегородок двухслойных",
      "unit_type": "100 м2",
      "cost_per_unit": 18450.75,
      "total_for_quantity": 18450.75,
      "materials_for_quantity": 11200.30,
      "difference_from_cheapest": 4618.73,
      "difference_percent": 33.39
    }
    // ... отсортировано по возрастанию стоимости
  ]
}
```

**Когда использовать:**
- Выбор оптимального варианта из нескольких технологий
- Анализ экономии при разных решениях
- Подготовка вариантов для заказчика

**Пример N8N Decision Workflow:**
```
1. HTTP Request (compare_variants)
2. IF Node (check if difference_percent > 20%)
   - TRUE: Send notification "Дорогой вариант!"
   - FALSE: Approve automatically
```

---

### 5. `find_similar_rates` - Поиск альтернативных расценок

**Назначение:** Найти похожие расценки (аналоги) для заданной

**Входные параметры:**
```json
{
  "rate_code": "10-05-001-01",
  "max_results": 5              // опционально, по умолчанию 5, макс 20
}
```

**Выходные данные:**
```json
{
  "success": true,
  "source_rate": "10-05-001-01",
  "count": 5,
  "alternatives": [
    {
      "rate_code": "10-05-001-01",
      "rate_full_name": "Устройство перегородок однослойных (исходная)",
      "unit_type": "100 м2",
      "cost_per_unit": 13832.02,
      "total_for_quantity": 13832.02,
      "materials_for_quantity": 8506.40,
      "difference_from_cheapest": 0.00,
      "difference_percent": 0.00
    },
    {
      "rate_code": "10-05-002-01",
      "rate_full_name": "Устройство перегородок с шумоизоляцией",
      "unit_type": "100 м2",
      "cost_per_unit": 15200.50,
      "total_for_quantity": 15200.50,
      "materials_for_quantity": 9800.20,
      "difference_from_cheapest": 1368.48,
      "difference_percent": 9.89
    }
    // ... отсортировано по возрастанию стоимости
  ]
}
```

**Когда использовать:**
- Поиск более дешевых аналогов
- Предложение альтернативных технологий
- Оптимизация сметы

**Пример N8N Optimization Workflow:**
```
1. Loop over all rates in estimate
2. For each rate:
   - HTTP Request (find_similar_rates)
   - Filter alternatives with difference_percent < 0 (cheaper)
   - If found: Send suggestion to user
```

---

## Готовые N8N Workflow Patterns

### Pattern 1: Чат-бот для расчета стоимости

```
┌─────────────────┐
│ Telegram/Slack  │ Получить вопрос пользователя
│ Trigger         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ OpenAI Node     │ Извлечь: description, quantity
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HTTP Request    │ Tool: quick_calculate
│ (MCP)           │ Body: { rate_identifier, quantity }
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Function Node   │ Форматировать ответ для пользователя
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram/Slack  │ Отправить результат
│ Send Message    │
└─────────────────┘
```

**Пример кода Function Node:**
```javascript
const result = $input.item.json;

if (result.success) {
  const message = `
📊 Расчет стоимости

Расценка: ${result.rate_info.rate_code}
Описание: ${result.rate_info.rate_full_name}

Объем: ${result.quantity} ${result.rate_info.unit_type}
Стоимость за единицу: ${result.cost_per_unit.toFixed(2)} руб.

💰 ИТОГО: ${result.calculated_total.toFixed(2)} руб.

Из них:
📦 Материалы: ${result.materials.toFixed(2)} руб.
⚙️ Работа + техника: ${result.resources.toFixed(2)} руб.
  `;

  return { json: { message } };
} else {
  return { json: { message: `❌ Ошибка: ${result.error}` } };
}
```

---

### Pattern 2: Автоматическое сравнение вариантов

```
┌─────────────────┐
│ Webhook         │ Получить список rate_codes + quantity
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HTTP Request    │ Tool: compare_variants
│ (MCP)           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Sort Node       │ Сортировать по total_for_quantity
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Function Node   │ Создать таблицу сравнения
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Google Sheets   │ Записать результаты
└─────────────────┘
```

---

### Pattern 3: Оптимизация сметы

```
┌─────────────────┐
│ Google Sheets   │ Читать все расценки из сметы
│ Read            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Loop Node       │ Для каждой расценки:
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HTTP Request    │ Tool: find_similar_rates
│ (MCP)           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Filter Node     │ Оставить только более дешевые
└────────┬────────┘   (difference_from_cheapest < 0)
         │
         ▼
┌─────────────────┐
│ IF Node         │ Если найдены более дешевые:
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
   YES       NO
    │         │
    ▼         ▼
┌───────┐  ┌───────┐
│ Email │  │ Skip  │
│ Alert │  └───────┘
└───────┘
```

---

### Pattern 4: Поиск + Детализация + Отчет

```
┌─────────────────┐
│ Manual Trigger  │ Ввести описание работ
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HTTP Request    │ Tool: natural_search
│ (MCP)           │ Найти подходящие расценки
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Item Lists      │ Взять первый результат
│ (First Item)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HTTP Request    │ Tool: show_rate_details
│ (MCP)           │ Получить детализацию
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Function Node   │ Сформировать PDF-отчет (HTML)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Email Node      │ Отправить отчет
└─────────────────┘
```

---

## Обработка ошибок в N8N

Все инструменты возвращают ошибки в формате:

```json
{
  "error": "Invalid input",
  "details": "Quantity must be greater than 0, got: -10"
}
```

**Рекомендуемая обработка:**

```javascript
// Function Node для проверки ответа
const result = $input.item.json;

if (result.error) {
  // Логировать ошибку
  console.error('MCP Tool Error:', result.error, result.details);

  // Вернуть понятное сообщение пользователю
  return {
    json: {
      success: false,
      user_message: `Не удалось выполнить запрос: ${result.details}`
    }
  };
}

// Если успешно - продолжить workflow
return { json: result };
```

**IF Node для маршрутизации:**
```
Condition: {{ $json.error }} is not empty
- TRUE branch: Send error notification
- FALSE branch: Continue processing
```

---

## Лучшие практики

### 1. Кэширование результатов

Используйте N8N Cache Node для частых запросов:

```
┌─────────────────┐
│ Cache Check     │ Проверить кэш по rate_code
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
  MISS       HIT
    │         │
    ▼         ▼
┌───────┐  ┌───────┐
│ MCP   │  │ Return│
│ Call  │  │ Cache │
└───┬───┘  └───────┘
    │
    ▼
┌───────┐
│ Cache │
│ Save  │
└───────┘
```

### 2. Batch Processing

Для обработки множества расценок используйте Loop Node:

```javascript
// Split Into Batches Node
{
  "batchSize": 10,  // Обрабатывать по 10 расценок за раз
  "options": {
    "reset": false  // Не сбрасывать между итерациями
  }
}
```

### 3. Retry логика

Настройте HTTP Request Node для повторных попыток:

```json
{
  "retry": {
    "maxRetries": 3,
    "retryInterval": 1000
  },
  "timeout": 30000
}
```

### 4. Валидация входных данных

Используйте Function Node перед вызовом MCP:

```javascript
// Валидация quantity
const quantity = parseFloat($json.quantity);

if (isNaN(quantity) || quantity <= 0) {
  throw new Error('Invalid quantity: must be a positive number');
}

// Валидация rate_code
const rateCode = ($json.rate_code || '').trim();

if (!rateCode) {
  throw new Error('Rate code cannot be empty');
}

return {
  json: {
    rate_code: rateCode,
    quantity: quantity
  }
};
```

---

## Примеры реальных Use Cases

### Use Case 1: Telegram-бот для прорабов

**Задача:** Прораб на объекте спрашивает стоимость работ через Telegram

**Workflow:**
1. Telegram Trigger (получить сообщение)
2. OpenAI (извлечь structured data: work_description, quantity)
3. HTTP Request → `quick_calculate`
4. Function (форматировать в читаемый вид)
5. Telegram Send Message

**Пример диалога:**
```
Прораб: Сколько стоит залить 25 кубов бетона М300?

Бот:
💰 Стоимость работ:

Расценка: ГЭСНп06-01-001-05
Бетон монолитный М300

Объем: 25 м³
Стоимость: 125,450.50 руб.

📦 Материалы: 95,600.00 руб.
⚙️ Работа: 29,850.50 руб.
```

---

### Use Case 2: Система оптимизации смет

**Задача:** Еженочно проверять все сметы и находить возможности экономии

**Workflow:**
1. Schedule Trigger (каждую ночь в 3:00)
2. Google Sheets Read (все активные сметы)
3. Loop:
   - Для каждой расценки → `find_similar_rates`
   - Filter (только более дешевые аналоги)
   - Calc (потенциальная экономия)
4. Aggregate (суммировать экономию)
5. Email (отправить отчет менеджеру)

**Результат:** "Найдено 12 оптимизаций, потенциальная экономия: 245,000 руб."

---

### Use Case 3: Автоматическая проверка КП подрядчиков

**Задача:** Проверить расценки от подрядчика на адекватность

**Workflow:**
1. Email Trigger (получить КП в PDF)
2. PDF Extract (извлечь таблицу работ)
3. Loop over rows:
   - HTTP Request → `quick_calculate` (для того же объема)
   - Compare (цена подрядчика vs. база данных)
   - IF (разница > 15%) → Flag as "Overpriced"
4. Generate Report (HTML/PDF)
5. Email (отправить результат проверки)

---

## Troubleshooting

### Проблема: Connection timeout

**Причина:** MCP сервер не отвечает
**Решение:**
```bash
# Проверить статус контейнера
docker-compose -f docker-compose.mcp.yml ps

# Проверить логи
docker-compose -f docker-compose.mcp.yml logs -f mcp-server

# Перезапустить
docker-compose -f docker-compose.mcp.yml restart
```

### Проблема: Tool returns empty results

**Причина:** Не найдено совпадений в базе
**Решение:**
- Упростить поисковый запрос
- Использовать более общие термины
- Проверить правильность написания (используйте кириллицу)

### Проблема: Incorrect total cost

**Причина:** Неправильная единица измерения
**Решение:**
- Проверить `unit_type` в ответе
- Если расценка "100 м²", а нужно 150 м², передавать quantity=150 (не 1.5)

---

## API Reference Summary

| Tool | Primary Use | Input | Output |
|------|-------------|-------|--------|
| `natural_search` | Поиск по описанию | query, unit_type?, limit? | List of rates |
| `quick_calculate` | Быстрый расчет | rate_identifier, quantity | Total cost + breakdown |
| `show_rate_details` | Детальная смета | rate_code, quantity? | Resources breakdown |
| `compare_variants` | Сравнение вариантов | rate_codes[], quantity | Comparison table |
| `find_similar_rates` | Поиск аналогов | rate_code, max_results? | Similar rates list |

---

## Дополнительные ресурсы

- **MCP Server Health:** `http://host.docker.internal:8003/health`
- **Database:** 28,686 расценок, 294,883 ресурсов
- **Supported units:** м², м³, т, м.п., 100 м², 1000 шт, и др.
- **Language:** Все запросы и ответы на русском языке

---

**Версия:** 1.0
**Дата:** 2025-10-21
**Статус:** Production Ready ✅
