# N8N → MCP Server Connection Guide

## Проблема
N8N и MCP Server работают в разных Docker сетях и не могут быть объединены в одну сеть.

## Решение: Host Network Bridge

Используйте `host.docker.internal` для доступа из N8N к MCP серверу на хост-машине.

## Настройка подключения в N8N

### Endpoint Configuration
```
MCP Server URL: http://host.docker.internal:8002/sse
Health Check:   http://host.docker.internal:8003/health
```

### Сетевая архитектура
```
┌─────────────────────────────────────────────────────┐
│ Host Machine (localhost)                            │
│                                                     │
│  ┌──────────────────────┐   ┌──────────────────┐  │
│  │ N8N Container        │   │ MCP Container    │  │
│  │ Network: n8n_n8n-    │   │ Network: n8npip- │  │
│  │         network      │   │         lines-   │  │
│  │                      │   │         bim_mcp- │  │
│  │ Port: 5678           │   │         network  │  │
│  └──────────────────────┘   └──────────────────┘  │
│           │                          │             │
│           │                          │             │
│           ▼                          ▼             │
│  ┌─────────────────────────────────────────────┐  │
│  │         Host Ports (Docker Port Mapping)    │  │
│  │  5678 → N8N                                 │  │
│  │  8002 → MCP SSE endpoint                    │  │
│  │  8003 → MCP Health Check                    │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  Connection: N8N → host.docker.internal:8002      │
└─────────────────────────────────────────────────────┘
```

## Тестирование подключения

### 1. Проверка доступности MCP с хоста
```bash
# Health check
curl http://localhost:8003/health

# Ожидаемый ответ:
# {"status": "healthy", "database": "connected", "timestamp": "..."}
```

### 2. Проверка доступности MCP из контейнера N8N
```bash
# Из контейнера N8N
docker exec n8n wget -O- http://host.docker.internal:8003/health

# Ожидаемый ответ:
# {"status": "healthy", "database": "connected", "timestamp": "..."}
```

### 3. Проверка SSE endpoint
```bash
# SSE endpoint (должен вернуть Server-Sent Events stream)
curl http://localhost:8002/sse
```

## Доступные MCP Tools

После подключения N8N получит доступ к 5 инструментам:

1. **natural_search** - Полнотекстовый поиск строительных расценок
   - Поиск по описанию работ на русском языке
   - Использует FTS5 для быстрого поиска

2. **quick_calculate** - Автоматический калькулятор стоимости
   - Принимает код расценки или описание
   - Возвращает стоимость с разбивкой по ресурсам

3. **show_rate_details** - Детальная информация о расценке
   - Полный состав ресурсов
   - Материалы, машины, труд

4. **compare_variants** - Сравнение нескольких расценок
   - Сравнение по стоимости
   - Оптимизация выбора

5. **find_similar_rates** - Поиск альтернативных расценок
   - Поиск более дешевых аналогов
   - Similarity search

## Примеры использования в N8N

### Workflow 1: Поиск расценки
```
HTTP Request → MCP Tool (natural_search)
Input: "монтаж перегородок из гипсокартона"
Output: Список найденных расценок
```

### Workflow 2: Расчет стоимости
```
HTTP Request → MCP Tool (quick_calculate)
Input: {code: "10-05-001-01", quantity: 150}
Output: Полная стоимость работ
```

## Troubleshooting

### Проблема: Connection refused
**Решение:** Проверьте что MCP контейнер запущен
```bash
docker-compose -f docker-compose.mcp.yml ps
```

### Проблема: Timeout
**Решение:** Проверьте порты в docker-compose.mcp.yml
```yaml
ports:
  - "8002:8000"   # MCP SSE endpoint
  - "8003:8001"   # Health check
```

### Проблема: host.docker.internal не резолвится
**Решение (Linux):** Добавьте в docker-compose.yml N8N:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

**Решение (Mac/Windows):** Уже работает из коробки

## Альтернативные решения (не рекомендуется)

### Вариант 1: External network (если нужна одна сеть)
Создайте общую external сеть, но это нарушает изоляцию.

### Вариант 2: Network mode host
Запустите MCP в режиме `network_mode: host`, но это снижает безопасность.

### Вариант 3: Reverse proxy
Используйте nginx/traefik, но это избыточно для локальной разработки.

## Рекомендация

**Используйте host.docker.internal** - это стандартное решение Docker для кросс-сетевого взаимодействия контейнеров через хост.

---

**Статус:** ✅ Проверено и работает
**Дата:** 2025-10-21
**Версия MCP:** 2.0
**Версия N8N:** latest
