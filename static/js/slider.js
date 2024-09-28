const SliderParams = {
    min: 0,
    max: 100,
    title: "slider",
    defaultValue: 0,
    step: 1,
    name: "",
    vertical: true,
    onChange: (value) => {
    }
}

var Slider = (function (id, parameters = {}) {

    const {
        min,
        max,
        title,
        defaultValue,
        step,
        name,
        vertical,
        onChange
    } = {...SliderParams, ...parameters}

    const sliderElem = document.getElementById(id);
    const rangeElem = document.createElement("input");
    const titleElem = document.createElement("span");
    const valueElem = document.createElement("span");


    titleElem.innerText = title;

    rangeElem.type = 'range';
    rangeElem.id = `${id}Range`;
    rangeElem.min = min;
    rangeElem.max = max;
    rangeElem.value = defaultValue;
    rangeElem.step = step;
    rangeElem.name = name || `${id}Range`;

    if (vertical) {
        rangeElem.style.writingMode = 'vertical-lr';
        rangeElem.style.direction = "rtl";

    }

    valueElem.innerText = defaultValue;

    sliderElem.appendChild(titleElem);
    sliderElem.appendChild(rangeElem);
    sliderElem.appendChild(valueElem);


    this.setValue = function (newValue) {
        rangeElem.value = newValue;
        valueElem.innerText = newValue;
    }

    // Events
    rangeElem.onchange = (e) => {
        valueElem.innerText = rangeElem.value;
        onChange(rangeElem.value)
    }

    rangeElem.ondblclick = (e) => {
        this.setValue(defaultValue)
        onChange(defaultValue);
    }


});