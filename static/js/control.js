const ControlPanelParams = {
    onChange: (value) => {}
}

var ControlPanel = (function (id, params={}) {


    const {onChange} = {...ControlPanelParams, ...params};

    elem = document.getElementById(id);

    const buttons = [
        {value: "FORWARD_LT", label: "Forward LT"},
        {value: "FORWARD", label: "Forward"},
        {value: "FORWARD_RT", label: "Forward RT"},
        {value: "LEFT", label: "Left"},
        {value: "STOP", label: "Stop"},
        {value: "RIGHT", label: "Right"},
        {value: "BACKWARD_LT", label: "Backward LT"},
        {value: "BACKWARD", label: "Backward"},
        {value: "BACKWARD_RT", label: "Backward RT"},
    ]


    let currentValue = "";
    let previousValue = "";

    const handleClick = (e,value,index) => {
        previousValue = currentValue;
        currentValue = value;
        // console.log(`${previousValue} : ${currentValue}`);
        if(previousValue === currentValue) {
            document.getElementById(previousValue).style.opacity = 1.0;
            currentValue="STOP"
        } else {
            if(currentValue !== "STOP") {
                document.getElementById(currentValue).style.opacity = 0.5;
            }
            if(previousValue) {
                document.getElementById(previousValue).style.opacity = 1.0;
            }
        }
        onChange(currentValue);

    }

    for(i=0; i<buttons.length; i++) {
        const v = buttons[i].value;
        const l = buttons[i].label;
        let e = document.createElement("button");
        e.id=v
        e.innerText=buttons[i].label;
        e.className="button button-blue";
        if(v==="STOP") {
            e.style.background="#ff0000"
        }
        e.onclick = (e) => {handleClick(e,v,i)};
        elem.appendChild(e)
    }

});

