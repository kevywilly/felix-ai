const ControlPanelParams = {
    onChange: (value) => {}
}

var ControlPanel = (function (id, params={}) {


    const {onChange} = {...ControlPanelParams, ...params};

    elem = document.getElementById(id);

    const buttons = [
        {value: 135, label: "ForwardLT"},
        {value: 90.0, label: "Forward"},
        {value: 45.0, label: "ForwardRT"},
        {value: 180.0, label: "Left"},
        {value: null, label: "Stop"},
        {value: 225.0, label: "BackwardLT"},
        {value: 270.0, label: "Backward"},
        {value: 315.0, label: "BackwardRT"}
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
        e.className="button button-blue text-base";
        if(v==="STOP") {
            e.style.background="#ff0000"
        }
        e.onclick = (e) => {handleClick(e,v,i)};
        elem.appendChild(e)
    }

});

