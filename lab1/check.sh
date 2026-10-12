#!/bin/bash

echo "HTTP → HTTPS"
curl -sSI http://localhost

echo "Статика через alias"
curl -ksSI https://localhost/static/style.css

echo "Балансировка"
for i in 1 2 3 4 5 6; do
  curl -ks -D - -o /dev/null https://localhost/api/recipes | grep -i '^X-Backend-ID:'
done

echo "Basic Auth без пароля — ожидается 401"
curl -ks -o /dev/null -w 'status=%{http_code}\n' https://localhost/admin

echo "404"
curl -ks -o /dev/null -w 'status=%{http_code}\n' https://localhost/нет-такой-страницы

echo "Второй виртуальный хост — ожидается 200"
curl -ks --resolve other.test:443:127.0.0.1 -o /dev/null -w 'status=%{http_code}\n' https://other.test/

echo "Неизвестный домен — ожидается 404"
curl -ks --resolve foreign.test:443:127.0.0.1 -o /dev/null -w 'status=%{http_code}\n' https://foreign.test/

echo "Лимит запросов — среди ответов ожидается 429"
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -ks -o /dev/null -w '%{http_code}\n' https://localhost/api/recipes
done