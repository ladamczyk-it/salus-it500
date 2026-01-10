# Home Assistant custom integration for Salus iT500
Since I've didn't find anything that will support my current home thermostat and setup (thermostat + water heater), based on [salusfy](https://github.com/floringhimie/salusfy) and couple of other inspirations (since I'm python newbie) I've created this custom component.

### Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ladamczyk-it&repository=https%3A%2F%2Fgithub.com%2Fladamczyk-it%2Fsalus-it500&category=climate%2C+water_heater)

or manually copy contents of `custom_components/salus_it500` into `config/custom_components/salus_it500`

### Usage
Edit your `config/configuration.yaml` and add there:
```
salus_it500:
  username: "EMAIL"
  password: "PASSWORD"
  id: "DEVICEID"
  platforms:
    - climate
    - water_heater
```
where EMAIL and PASSWORD are credentials for mobile app or [https://salus-it500.com](https://salus-it500.com) login. In order to obtain DEVICEID you need to access mentioned Salus page, login, select device and copy `devId` from URL params:
![image](https://user-images.githubusercontent.com/33951255/140301260-151b6af9-dbc4-4e90-a14e-29018fe2e482.png)

Last piece is selecting right platforms for you, supported are `climate` and `water_heater`. Enjoy your automation.