let snapshots = { forward: 0, left: 0, right: 0 };

let strafe = false;
let capture = false;
let autodrive = false;
let autonav = false;

let joyData = { x: 0, y: 0, strafe: strafe };

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
    $(`#${id}`).text(`${label}: ${state ? "ON" : "OFF"}`);
}


const displaySnapshots = (data) => {
    snapshots = data;
    $("#btnLeft").text(`Left: ${snapshots.left}`);
    $("#btnForward").text(`Forward: ${snapshots.forward}`);
    $("#btnRight").text(`Right: ${snapshots.right}`);
}

const getSnapshots = () => {
    get("api/snapshots/ternary", displaySnapshots);
}

const createSnapshot = (label) => {
    post(
        `api/snapshots/ternary/${label}`, null, displaySnapshots);
}

const handleJoystick = (stickData) => {
    joyData = {x: parseFloat(stickData.x)/100.0, y: parseFloat(stickData.y)/100.0, strafe: strafe}
    post("api/joystick", joyData);
}

$(function () {
    $("#btnLeft").on("click", () => {
        createSnapshot("left");
    })
    $("#btnRight").on("click", () => {
        createSnapshot("right");
    })
    $("#btnForward").on("click", () => {
        createSnapshot("forward");
    })

    $("#btnStrafe").on("click", () => {
        strafe = !strafe;
        displayToggleButton("btnStrafe", strafe, "Strafe");
    })
    $("#btnAutoDrive").on("click", () => {
        autodrive = !autodrive;
        displayToggleButton("btnAutoDrive", autodrive, "Auto Drive");
    })
    $("#btnAutoNav").on("click", () => {
        autonav = !autonav;
        displayToggleButton("btnAutoNav", autonav, "Auto Nav");
    })
    $("#btnCapture").on("click", () => {
        capture = !capture;
        displayToggleButton("btnCapture", capture, "Capture");
    })
   
    getSnapshots()

    displayToggleButton("btnStrafe", strafe, "Strafe");
    displayToggleButton("btnCapture", capture, "Capture");
    displayToggleButton("btnAutoDrive", autodrive, "Auto Drive");
    displayToggleButton("btnAutoNav", autonav, "Auto Nav");

});

var joy1 = new JoyStick('joy1', {
    "title": "Control",
    internalFillColor: "#0000FF",
    externalStrokeColor: "#0000FF",
}, handleJoystick);

