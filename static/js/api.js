const NAVZERO = { x: 0, y: 0, w: 0, h: 0 }
const SNAPSHOT_FOLDER = 'ternary'


let snapshots = { forward: 0, left: 0, right: 0 };

let strafe = false;
let autodrive = false;
let captureMode = false;
let driveMode = false;

let prevJoyData = { x: 0, y: 0, strafe: strafe };
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
       if(!(joyData.x == 0 && joyData.y == 0)) {
              return;
       }
    }
    prevJoyData = {...joyData}
    post("api/joystick", joyData, (data) => {
        console.log(data);
    });
}
const stop = () => {
    joyData = { x: 0, y: 0, strafe: strafe }
    applyJoyData();
}

const handleJoystick = (stickData) => {
    joyData = { x: parseFloat(stickData.x) / 100.0, y: parseFloat(stickData.y) / 100.0, strafe: strafe }
    applyJoyData();
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
}, handleJoystick);


const displayCoordinates = (x,y,w,h) => {
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
        request = { x,y,w,h };
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

    $("#btnStrafe").on("click", () => {
        strafe = !strafe;
        displayToggleButton("btnStrafe", strafe, "Strafe");
    })
    $("#btnAutoDrive").on("click", () => {
        autodrive = !autodrive;
        displayToggleButton("btnAutoDrive", autodrive, "Auto Drive");
    })
    $("#btnAutoNav").on("click", () => {
        driveMode = !driveMode;
        displayToggleButton("btnAutoNav", driveMode, "Auto Nav");
    })
    $("#btnCapture").on("click", () => {
        captureMode = !captureMode;
        displayToggleButton("btnCapture", captureMode, "Capture");
    })

    $("#navImage").on("dblclick", () => {
        stop();
    })

    $('#navImage').on("click", handleNavImageClick)

    getSnapshots()

    displayToggleButton("btnStrafe", strafe, "Strafe");
    displayToggleButton("btnCapture", captureMode, "Capture");
    displayToggleButton("btnAutoDrive", autodrive, "Auto Drive");
    displayToggleButton("btnAutoNav", driveMode, "Auto Nav");
    displayCoordinates("-","-","-","-");

});




