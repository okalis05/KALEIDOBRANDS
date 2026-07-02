const searchBox = document.querySelector(".catalog-search-input");
const results = document.getElementById("liveResults");

if (searchBox) {

    searchBox.addEventListener("keyup", function(){

        let q = this.value;

        if(q.length < 2){

            results.innerHTML = "";
            return;

        }

        fetch("/products/api/search/?q="+encodeURIComponent(q))

        .then(r=>r.json())

        .then(data=>{

            let html="";

            data.forEach(product=>{

                html += `
                    <a href="${product.url}" class="live-item">

                        <strong>${product.name}</strong>

                        <small>${product.category}</small>

                    </a>
                `;

            });

            results.innerHTML=html;

        });

    });

}