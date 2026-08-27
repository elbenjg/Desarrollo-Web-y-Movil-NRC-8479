
const peliculasPorDefecto = [
    {"id": 1,"nombre": "Spider-Man", "Año": 2002, "valoracion": 4, "imagen": "https://es.web.img2.acsta.net/medias/nmedia/18/90/04/41/20078157.jpg"},
    {"id": 2,"nombre": "Spider-Man 2", "Año": 2004, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/M/MV5BNGQ0YTQyYTgtNWI2YS00NTE2LWJmNDItNTFlMTUwNmFlZTM0XkEyXkFqcGc@._V1_.jpg"},
    {"id": 3,"nombre": "Spider-Man 3", "Año": 2007, "valoracion": 3, "imagen": "https://m.media-amazon.com/images/M/MV5BODE2NzNhMDctYjUzMC00Y2M5LWI2Y2EtODJkZTFjN2Y5ODlmXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"},
    {"id": 4,"nombre": "The Shining", "Año": 1980, "valoracion": 5, "imagen": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSsfuzIEX8nD_OMJ6AwZ-awygwtojO_W3YtLTCh4xmk_xIlXy9CXR9qN_s3&s=10"},
    {"id": 5,"nombre": "Coraline", "Año": 2009, "valoracion": 4, "imagen": "https://covers.storytel.com/jpg-640/9780060735562.511611c4-0530-4a11-bd6d-bb6fce9dc492?optimize=high"},
    {"id": 6,"nombre": "The Matrix", "Año": 1999, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/I/51EG732BV3L._AC_.jpg"},
    {"id": 7,"nombre": "The End of Evangelion", "Año": 1997, "valoracion": 5, "imagen": "https://static.wikia.nocookie.net/evangelion/images/1/18/Eva_theend.jpg/revision/latest?cb=20110607194500&path-prefix=es"},
    {"id": 8,"nombre": "Evangelion: 1.0 You Are (Not) Alone", "Año": 2007, "valoracion": 4, "imagen": "https://m.media-amazon.com/images/M/MV5BMTg1MmRkZDItNjQxMi00MjY4LThkZTAtZWQyNGNkMTc0MDYwXkEyXkFqcGc@._V1_.jpg"},
    {"id": 9,"nombre": "Evangelion: 2.0 You Can (Not) Advance", "Año": 2009, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/M/MV5BZWZiNjcyNjAtZmZhOC00NDk0LTg1ZGMtYWM4MGYxNmY0ZDVlXkEyXkFqcGc@._V1_.jpg"},
    {"id": 10,"nombre": "The Tale of The Princess Kaguya", "Año": 2013, "valoracion": 5, "imagen": "https://resizing.flixster.com/-XZAfHZM39UwaGJIFWKAE8fS0ak=/v3/t/assets/p10922577_p_v8_aa.jpg"},
    {"id": 11,"nombre": "Princess Mononoke", "Año": 1997, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/M/MV5BZTcyN2Y0MDYtMGI1NC00MWQ1LWFhZGMtN2U4NTcxZGYyNjljXkEyXkFqcGc@._V1_.jpg"},
    {"id": 12,"nombre": "The Shawshank Redemption", "Año": 1994, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/M/MV5BMDAyY2FhYjctNDc5OS00MDNlLThiMGUtY2UxYWVkNGY2ZjljXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"},
    {"id": 13,"nombre": "The Godfather", "Año": 1972, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/M/MV5BNGEwYjgwOGQtYjg5ZS00Njc1LTk2ZGEtM2QwZWQ2NjdhZTE5XkEyXkFqcGc@._V1_.jpg"},
    {"id": 14,"nombre": "The Dark Knight", "Año": 2008, "valoracion": 5, "imagen": "https://m.media-amazon.com/images/M/MV5BMTMxNTMwODM0NF5BMl5BanBnXkFtZTcwODAyMTk2Mw@@._V1_.jpg"},
    {"id": 15,"nombre": "Pulp Fiction", "Año": 1994, "valoracion": 5, "imagen": "https://es.web.img3.acsta.net/img/05/66/05663f00b8b5df58b003aaf5c46ef8ad.jpg"}
];


let catalogoActual = JSON.parse(localStorage.getItem('misPeliculas')) || peliculasPorDefecto;

const Peliculas = {
    "status": 200,
    "message": "Productos obtenidos correctamente",
    "data": catalogoActual
};



function actualizarImagen(urlImagen) {
    const imagenSeleccionada = document.getElementById("imagen-seleccionada");
    if(imagenSeleccionada) {
        imagenSeleccionada.src = urlImagen;
        imagenSeleccionada.style.display = "block";
    }
}

function actualizarCalificacion(pelicula) {
    const calificacion = document.getElementById("calificacion");
    if(!calificacion) return;

    let estrellasHTML = '';
    for (let i = 1; i <= 5; i++) {
        if (i <= pelicula.valoracion) {
            estrellasHTML += '<span style="color: #FFD700; font-size: 2.8rem;">★</span>';
        } else {
            estrellasHTML += '<span style="color: #ccc; font-size: 2.8rem;">☆</span>';
        }
    }

    calificacion.innerHTML = `
        <p class="mb-1" style="font-size: 2.5rem;"><strong>Año:</strong> ${pelicula.Año}</p>
        <div class="mt-2">${estrellasHTML}</div>
    `;
}

function manejarSeleccionPelicula(pelicula) {
    actualizarImagen(pelicula.imagen);
    actualizarCalificacion(pelicula);
    
    const nombreElemento = document.getElementById("nombre-pelicula");
    if(nombreElemento) {
        nombreElemento.textContent = pelicula.nombre;
    }
}

function cargarListaPeliculas() {
    const listaPeliculas = document.getElementById("lista-peliculas");
    if(!listaPeliculas) return;


    listaPeliculas.innerHTML = '';

    Peliculas.data.forEach(pelicula => {
        let li = document.createElement("li");
        let a = document.createElement("a");
        
        a.className = "dropdown-item";
        a.href = "#";
        a.textContent = pelicula.nombre;

        a.addEventListener("click", function(e) {
            e.preventDefault(); 
            manejarSeleccionPelicula(pelicula);
        });

        li.appendChild(a);
        listaPeliculas.appendChild(li);
    });
}



function guardarNuevaPelicula(evento) {
    evento.preventDefault();

    const nombre = document.getElementById("nombre").value;
    const imagen = document.getElementById("imagen").value;
    const año = document.getElementById("año").value;
    const calificacion = document.getElementById("calificacion").value;

    const nuevaPelicula = {
        id: Peliculas.data.length + 1,
        nombre: nombre,
        Año: parseInt(año),
        valoracion: parseInt(calificacion),
        imagen: imagen
    };


    Peliculas.data.push(nuevaPelicula);

    localStorage.setItem('misPeliculas', JSON.stringify(Peliculas.data));

    document.getElementById("formulario-pelicula").reset();
    alert("¡Película agregada con éxito! Ve al inicio para verla en el menú.");
}

function cargarCatalogo() {
    const contenedorCatalogo = document.getElementById("catalogo-peliculas");
    if (!contenedorCatalogo) return; 

    contenedorCatalogo.innerHTML = ''; 

    Peliculas.data.forEach(pelicula => {
        let estrellasHTML = '';
        for (let i = 1; i <= 5; i++) {
            if (i <= pelicula.valoracion) {
                estrellasHTML += '<span style="color: #FFD700; font-size: 1.5rem;">★</span>';
            } else {
                estrellasHTML += '<span style="color: #ccc; font-size: 1.5rem;">☆</span>';
            }
        }

        const tarjeta = document.createElement("div");
        tarjeta.className = "col-md-4 col-lg-3 mb-4"; // 4 columnas en PC, 3 en tablets
        
        tarjeta.innerHTML = `
            <div class="card h-100 shadow-sm border-0" style="background-color: #07176E; color: white;">
                <img src="${pelicula.imagen}" class="card-img-top mx-auto mt-3 rounded" alt="${pelicula.nombre}" style="object-fit: cover; height: 350px; width: 90%;">
                <div class="card-body text-center">
                    <h5 class="card-title fw-bold">${pelicula.nombre}</h5>
                    <p class="card-text mb-1" style="color: #61F2F5;">Año: ${pelicula.Año}</p>
                    <div>${estrellasHTML}</div>
                </div>
            </div>
        `;
        
        contenedorCatalogo.appendChild(tarjeta);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    

    if (document.getElementById("lista-peliculas")) {
        cargarListaPeliculas();
    }

    const formulario = document.getElementById("formulario-pelicula");
    if (formulario) {
        formulario.addEventListener("submit", guardarNuevaPelicula);
    }

    if (document.getElementById("catalogo-peliculas")) cargarCatalogo();
});