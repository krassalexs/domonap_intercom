# Domonap Home Assistant Integration

![Logo](https://github.com/svmironov/domonap_intercom/blob/main/img/icon.png?raw=true)

Интеграция позволяет управлять устройствами привязанными к приложению Domonap (альтернативный провайдер домофона в домах ПИК) из Home Assistant

## Возможности

* Открытие дверей
* Загрузка видеопотока
* Получение уведомлений о входящих звонках
* Получение уведомлений из чата домофона

## Ограничения

* Существует ограничение одновременного использования на нескольких устройствах одного номера телефона
* ~~На текущий момент нет возможности получать уведомления о звонках~~
* ~~По неизвестной причине сервер может убивать сессии, для возобновления работы интеграции необходимо выполнить авторизацию заново~~  

## Установка

* Установите HACS
* Добавьте репозиторий https://github.com/svmironov/domonap_intercom в HACS 
* Найдите Domonap в поиске по интеграциям
* Установите нажав на кнопку "Установить" 
* Перезапустите сервер Home Assistant
* После добавьте итеграцию в настройках в пункте "Устройства и Службы"
* Авторизация выполняется по номеру телефона привязанному к приложению при регистрации

## Получение уведомлений

Интеграция испускает сигналы на которые можно подписаться в автоматизации:
1. ```domonap_incoming_call``` следующего содержания:
```yaml
event_type: domonap_incoming_call
data:
  EventMessage: DomofonCalling
  DoorId: 8452d508564e5a076c8122b6
  Address: Лифтовой холл
  CallId: "154543486.54786447"
  VideoUrl: https://hls.domonap.ru/8452d508564e5a076c8122b6/index.m3u8
  HttpVideoUrl: https://hls.domonap.ru/8452d508564e5a076c8122b6/index.m3u8
  VideoPreview: >-
    https://api.domonap.ru/video-api/preview/Device/8452d508564e5a076c8122b6/qQtfsMiQYS0YuD8LLKrDGbPijncAShubrISKMs7E1cw
  SipAccount: "1000457231"
  SipPassword: 8452d508564e5a076c8122b6
  SipDomain: asterisk-2.domonap.ru
  SipPort: "7021"
  PushType: Domofon
  photoUrl: https://s3-api.domonap.ru/snapshot/154543486.54786447
origin: LOCAL
time_fired: "2025-06-18T15:10:58.919425+00:00"
```

2. ```domonap_receive_message``` следующего содержания:
```yaml
event_type: domonap_receive_message
data:
  id: 8452d508564e5a076c8122b6
  channel: username1-username
  text: "Текст сообщения"
  data: null
  sender: username1
  name: Username
  chatType: Private
  createdOn: "2025-06-18T15:02:32.1264693Z"
  isRead: false
  avatar: https://s3-api.domonap.ru/avatar/avatar
origin: LOCAL
time_fired: "2025-06-18T15:02:32.208782+00:00"
```

3. ```domonap_user_status_changed``` следующего содержания:
```yaml
event_type: domonap_user_status_changed
data:
  user: username1
  status: offline
origin: LOCAL
time_fired: "2025-06-18T15:07:23.395167+00:00"
```

Пример автоматизации уведомления о звонке в Telegram (настройка [Telegram](https://www.home-assistant.io/integrations/telegram_polling)):
```yaml
alias: Звонок из домофона в Telegram
description: ""
mode: single
triggers:
  - trigger: event
    event_type: domonap_incoming_call
    enabled: true
conditions: []
actions:
  - action: telegram_bot.send_photo
    data:
      caption: |-
        📞📲 Кто-то звонит в домофон
        📍 {{ trigger.event.data.Address }}
      url: "{{ trigger.event.data.photoUrl }}"
      inline_keyboard: "🔓 Открыть:/open_{{ trigger.event.data.DoorId }}"
```

## Отказ от ответственности

Данное программное обеспечение никак не связано и не одобрено ООО ДОМОНАП, владельца торговой марки ДОМОНАП. Используйте его на свой страх и риск. Автор ни при каких обстоятельствах не несёт ответственности за порчу или утрату вашего имущества и возможного вреда в отношении третьих лиц.

Все названия брендов и продуктов принадлежат их законным владельцам.
