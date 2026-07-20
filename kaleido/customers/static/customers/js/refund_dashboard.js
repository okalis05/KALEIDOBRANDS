const daily =
JSON.parse(
document.getElementById(
"daily-data"
).textContent
);

const status =
JSON.parse(
document.getElementById(
"status-data"
).textContent
);

const reasons =
JSON.parse(
document.getElementById(
"reason-data"
).textContent
);

const statusData = JSON.parse(
    document.getElementById("status-data").textContent
);

new Chart(

document.getElementById(
"dailyRefundChart"
),

{

type:"line",

data:{

labels:

daily.map(
d=>d.day
),

datasets:[{

label:"Refunds",

data:

daily.map(
d=>d.total
),

fill:false,

borderWidth:3,

tension:.3

}]

}

});



new Chart(

document.getElementById(
"statusChart"
),

{

type:"pie",

data:{

labels:

status.map(
s=>s.status
),

datasets:[{

data:

status.map(
s=>s.total
)

}]

}

});



new Chart(

document.getElementById(
"reasonChart"
),

{

type:"bar",

data:{

labels:

reasons.map(
r=>r.reason
),

datasets:[{

label:"Refund Requests",

data:

reasons.map(
r=>r.total
)

}]

}

});

