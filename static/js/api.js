const NAVZERO = { x: 0, y: 0, w: 0, h: 0 }
const SNAPSHOT_FOLDER = 'ternary'

let snapshots = { forward: 0, left: 0, right: 0 };
let _power = 60;
let strafe = false;
let lockXY = false;
let autodrive = false;
let captureMode = false;
let driveMode = false;
const joyMin = 0.4

let prevJoyData = { x: 0, y: 0, strafe: strafe, power: _power / 100.0 };
let joyData = { x: 0, y: 0, strafe: strafe, power: _power / 100.0 };

const post = (url, data, callback = null) => {
    payload = JSON.stringify(data);
    $.ajax({
        method: "POST",
        url: url,
        data: payload,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        success: callback
    });
}

const get = (url, callback = null) => {
    $.ajax({
        method: "GET",
        dataType: "json",
        url: url,
        contentType: "application/json; charset=utf-8",
        success: callback,
    });
}

const displayToggleButton = (id, state, label) => {
    $(`#${id}`).css("background-color", state ? "green" : "#222222");

    $(`#${id}`).text(`${label}: ${state ? "ON" : "OFF"}`);
}


const displaySnapshots = (data) => {
    snapshots = data;
    $("#btnLeft").text(`Left: ${snapshots.left}`);
    $("#btnForward").text(`Forward: ${snapshots.forward}`);
    $("#btnRight").text(`Right: ${snapshots.right}`);
}

const getSnapshots = () => {
    get(`api/snapshots/${SNAPSHOT_FOLDER}`, displaySnapshots);
}

const createSnapshot = (label) => {
    post(
        `api/snapshots/ternary/${label}`, null, displaySnapshots);
}

const applyJoyData = () => {

    if (JSON.stringify(joyData) === JSON.stringify(prevJoyData)) {
        if (!(joyData.x == 0 && joyData.y == 0)) {
            return;
        }
    }
    prevJoyData = { ...joyData }

    post("api/joystick", { ...joyData }, (data) => {
        console.log(data);
    });
}
const stop = () => {
    joyData = { x: 0, y: 0, strafe: strafe }
    applyJoyData();
}

const dir_v = (v) => v < 0 ? -1 : 1;

const applyLockXY = () => {
    console.log(joyData)
    
    if(lockXY) {
        if(Math.abs(joyData.x) > Math.abs(joyData.y)) {
            joyData.y = 0;
        } else {
            joyData.x = 0;
        }
    }
    console.log("apply joy data")
    console.log(joyData)
}

const handleJoystick = (joyNum, stickData) => {
    strafe = (joyNum === 2);
    let x = (parseFloat(stickData.x) / 100.0);
    let y = (parseFloat(stickData.y) / 100.0);
    let power = _power / 100.0
    /*
    if( x !== 0)
        x = (Math.abs(x) * (1.0-joyMin) + joyMin)*dir_v(x);
    if (y !== 0)
        y = (Math.abs(y) * (1.0-joyMin) + joyMin)*dir_v(y);
    */

    joyData = { x, y, strafe, power }
    applyLockXY();
    applyJoyData();
}

const handleUpdatePower = (value) => {
    _power = value;
}

const captureButtons = [
    { id: "btnLeft", label: "left" },
    { id: "btnRight", label: "right" },
    { id: "btnForward", label: "forward" }
];

const joy1 = new JoyStick('joy1', {
    "title": "joy1",
    internalFillColor: "#656565",
    externalStrokeColor: "#999999",
}, (d) => handleJoystick(1, d));

const joy2 = new JoyStick('joy2', {
    "title": "joy2",
    internalFillColor: "#656565",
    externalStrokeColor: "#999999",
}, (d) => handleJoystick(2, d));


const powerSlider = new Slider(
    "powerSlider",
    {
        min: 0,
        max: 100,
        step: 5,
        defaultValue: _power,
        title: "Power",
        name: "power",
        vertical: true,
        onChange: handleUpdatePower
    }
);

const displayCoordinates = (x, y, w, h) => {
    $('#coordinatesDisplay').text(`x: ${x} y: ${y} w:${w} h:${h}`);
}

const handleNavImageClick = (event) => {
    const rect = event.target.getBoundingClientRect();

    // Calculate the x and y coordinates relative to the image
    const w = rect.width
    const h = rect.height
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    cmd = { x, y, w, h };

    if (captureMode || driveMode) {
        request = { x, y, w, h };
        post("api/navigate", request, (data) => {
            console.log(data);
        });
    }

    displayCoordinates(x, y, w, h);
}

$(function () {

    for (let button of captureButtons) {
        $(`#${button.id}`).on("click", () => {
            createSnapshot(button.label);
        });
    }

    $("#btnLockXY").on("click", () => {
        lockXY = !lockXY;
        displayToggleButton("btnLockXY", lockXY, "LockXY");
    })
    $("#btnAutoDrive").on("click", () => {
        autodrive = !autodrive;
        displayToggleButton("btnAutoDrive", autodrive, "Auto Drive");
        post("api/autodrive", {})
    })

    $("#navImage").on("dblclick", () => {
        stop();
    })

    $('#navImage').on("click", handleNavImageClick)

    getSnapshots()

    displayToggleButton("btnLockXY", lockXY, "Lock XY");
    //displayToggleButton("btnCapture", captureMode, "Capture");
    displayToggleButton("btnAutoDrive", autodrive, "Auto Drive");
    //displayToggleButton("btnAutoNav", driveMode, "Auto Nav");
    displayCoordinates("-", "-", "-", "-");

});




