const ControlPanelParams = {
    onChange: (value) => {}
}

var ControlPanel = (function (id, params={}) {


    const {onChange} = {...ControlPanelParams, ...params};

    elem = document.getElementById(id);

    const btnStop = {value: {x: 0, y: 0, strafe: false}, label: "Stop", id: "btnStop"};

    const buttons = [
        {value: {x: -1, y: 0.8, strafe: false}, label: "Forward Left", id: "btnTurnLeft"},
        {value: {x: 0, y: 1, strafe: false}, label: "Forward", id: "btnForward"},
        {value: {x: 1, y: 0.8, strafe: false}, label: "Forward Right", id: "btnTurnLRight"},
        {value: {x: -1, y: 0, strafe: true}, label: "Left", id: "btnLeft"},
        btnStop,
        {value: {x: 1, y: 0, strafe: true}, label: "Right", id: "btnRight"},
        {value: {x: -1, y: -0.8, strafe: false}, label: "Back Left", id: "btnBackLeft"},
        {value: {x: 0, y: 1, strafe: false}, label: "Backward", id: "btnBackward"},
        {value: {x: 1, y: -0.8, strafe: false}, label: "Back Right", id: "btnBackRight"},
    ]

   
    let selected = undefined

    const handleClick = (btn) => {
 
        if(selected){
            console.log(selected);
            document.getElementById(selected.id).style.opacity = 1.0; 
        }

        if(selected && (selected.id === btn.id)){
            selected = btnStop;
        } else {
            selected = btn;
        }
        
        onChange(selected);
        
        /*
        if(previous.id == current.id) {
            el.style.opacity = 1.0;
            current = btnStop;
            onChange(btnStop);
            return;
        }
        let previousEl = document.getElementById(previous.id);
        previousEl.style.opacity = 1.0;
        
        onChange(btn);
        */

    }

    for(i=0; i<buttons.length; i++) {
        const btn = buttons[i];
        let el = document.createElement("button");
        el.id=btn.id;
        el.innerText=btn.label

        el.className="button button-blue text-base";
        
        if(btn.id==="btnStop") {
            el.style.background="#ff0000"
        }
        
        el.onclick = () => {
            handleClick(btn);
        };
        
        elem.appendChild(el);
    }

});

