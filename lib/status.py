SENSOR_STATUS = {
    "control_board": {
        "connected": 0,
        "build-platform": -1,
        "level-tank": -1,
        "blade": -1,
        "print-blade": -1,
        "collect-blade": -1,
        "resin-pump": -1,
        "pneumatic-pump": -1,
        "autoleveling": 0
    },
    "temperature": {
        "connected": 0,
        "current": -1,
        "target": -1,
        "heating": 0
    },
    "waterlevel": {
        "connected": 0,
        "current": -1,
        "target": -1
    },
    "pressure":{
        "connected": 0,
        "current": -1,
        "target": -1
    },
    "engine": {
        "connected": 0,
        "ledon": 0,
        "ledtemp": {
            "left": -1,
            "right": -1,
            "one": -1
        }
    }
}

PRINT_STATUS = {
    "data-index": -1,
    "data": [],
    "recipe": "-",
    "current-layer": 0,
    "total-layer": 0,
    "remaining-time": 0,
    "progress": 0
}

DEVICE_STATUS = {
    "allow-remote-control": 0,
    "status": "OFFLINE",
    "selected":{
        "data": [],
        "recipe": "-"
    }
}

DEVICE_CONFIG = {
    "app-version": "-",
    "control-board": {
        "type": "-",
        "firmware-version": "-"
    },
    "temperature": "-",
    "pressure": "-",
    "waterlevel": "-",
    "engine": "-"
}

DEVICE_ALARM = {
    "subject": "-",
    "content": "-",
    "created_date": "0000:00:00:00:00:00"
}

DEVICE_REQUEST = {
    "request-list": []
}