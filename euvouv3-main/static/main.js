// main.js

$(document).ready(function() {

    // Painel de Rifas (painel.html)
    if ($('#selectRifa').length) {
        $('#selectRifa').on('change', handleSelectRifa);
    }

    if ($('#formAlterarPreco').length) {
        $('#formAlterarPreco').on('submit', handleAlterarPreco);
    }

    // Mascara de telefone no painel de dados
    if ($('#telefone').length) {
        const telInput = $('#telefone');
        telInput.val(formatTelefone(telInput.val()));
        telInput.on('input', function() {
            $(this).val(formatTelefone($(this).val()));
        });
    }

    // Permitir rolar listas de cards mesmo quando o mouse não está sobre elas
    const feed = $('.scroll-feed');
    if (feed.length) {
        $(document).on('wheel', function(e) {
            if ($(e.target).closest('.scroll-feed').length) return;
            feed.scrollTop(feed.scrollTop() + e.originalEvent.deltaY);
        });
    }
});

function handleSelectRifa() {
    const idRifa = $(this).val();
    $('#headerRifaPainel').remove();
    if (!idRifa) return $('#painelCartelas').hide();

    $.getJSON(`/api/rifa/${idRifa}`, function(rifa) {
        $('#painelCartelas').show();
        const container = $('#listaCartelas').html('');

        // Mostra todas as infos da rifa no header:
        let btnSorteio = '';
        if(rifa.pode_sortear){
            btnSorteio = `<button class="btn btn-danger mb-2" onclick="sortearRifa(${idRifa})">Sortear</button>`;
        }
        let vencedorInfo = '';
        if(rifa.status === 'finalizada'){
            vencedorInfo = `<p class="mb-1 text-success"><b>Ganhador:</b> ${rifa.vencedor_nome || ''} (#${rifa.numero_vencedor || ''})</p>`;
        }
        $('#painelCartelas').prepend(`
            <div class="card mb-4" id="headerRifaPainel">
                <div class="card-body">
                    <div class="d-flex flex-wrap justify-content-between align-items-center">
                        <div>
                            <h4 class="mb-1">Rifa: <span id="nomeRifaSelecionada">${rifa.titulo}</span></h4>
                            <p class="mb-1"><b>Prêmio:</b> ${rifa.descricao_premio || '-'}</p>
                            <p class="mb-1"><b>Preço por número:</b> R$ ${Number(rifa.valor_atual).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</p>
                            <p class="mb-1"><b>Data de início:</b> ${rifa.data_inicio || '-'}</p>
                            <p class="mb-1"><b>Data do sorteio:</b> ${rifa.data_fim || '-'}</p>
                            <p class="mb-1"><b>Limite de números:</b> ${rifa.limite_numeros || 'Ilimitado'}</p>
                            <p class="mb-1 text-success"><b>Total de Ingressos vendidos:</b> ${rifa.fichas_vendidas || 0}</p>
                            <p class="mb-1 text-success"><b>Valor arrecadado:</b> R$ ${Number(rifa.valor_total_vendido || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</p>
                            ${vencedorInfo}
                        </div>
                        <div class="text-end">
                            <button class="btn btn-outline-primary mb-2" onclick="gerarCartela(${idRifa})">Gerar Cartela</button>
                            <button class="btn btn-outline-secondary mb-2" onclick="gerarCartelaVendedor(${idRifa})">Gerar Cartela P/ Vendedor</button>
                            <button class="btn btn-outline-info mb-2" onclick="abrirModalAdicionarVendedor(${idRifa})">Adicionar Vendedor</button>
                            <button class="btn btn-outline-warning mb-2" onclick="abrirGerenciarVendedores(${idRifa})">Gerenciar Vendedores</button>
                            <button class="btn btn-outline-dark mb-2" onclick="alterarImagemFundoRifa(${idRifa})">Alterar Fundo</button>
                            ${btnSorteio}
                        </div>
                    </div>
                </div>
            </div>
        `);

        // Renderiza as cartelas da rifa selecionada
        $.getJSON(`/api/rifa/${idRifa}/cartelas`, function(cartelas) {
            if (cartelas.length === 0) {
                container.append('<div class="alert alert-info">Nenhuma cartela criada para esta rifa.</div>');
            }
            cartelas.forEach(cartela => {
                let nomes = cartela.criador.split(' ').slice(0, 2).join(' ');
                container.append(`
                    <div class="col-md-6">
                        <div class="card bg-light h-100 mb-3">
                            <div class="card-body">
                                <h5 class="card-title">Cartela de ${nomes} #${cartela.numero_cartela}</h5>
                                <p class="card-text">
                                    <b>Criador:</b> ${cartela.criador}<br>
                                    <b>Vendidos:</b> ${cartela.vendidos}
                                </p>
                                <button class="btn btn-primary btn-sm me-2 btn-ver-numeros" data-id="${cartela.id}" data-numero="${cartela.numero_cartela}">Ver Números</button>
                                <button class="btn btn-outline-warning btn-sm me-2" onclick="abrirAlterarPreco(${cartela.id_rifa})">Alterar Preço</button>
                                <button class="btn btn-outline-success btn-sm">Criar Cupom</button>
                            </div>
                        </div>
                    </div>
                `);
            });
        });
        $('#listaCartelas').on('click', '.btn-ver-numeros', function(){
            const id = $(this).data('id');
            const numero = $(this).data('numero');
            abrirNumeros(id, numero);
        });
    });
}


function abrirNumeros(idCartela, numeroCartela) {
    $('#modalNumerosLabel').text(`Cartela #${numeroCartela}`);
    $('#gradeNumeros').html('');
    $.getJSON(`/api/cartela/${idCartela}`, function(fichas) {
        fichas.forEach(function(ficha, idx) {
            let numeroAbsoluto = (numeroCartela - 1) * 50 + ficha.numero;
            $('#gradeNumeros').append(`
                <div class="col-6 col-sm-4 col-md-3 col-lg-2 mb-3">
                    <div class="border rounded p-2 text-center ${ficha.status == 'vendido' ? 'bg-danger text-white' : 'bg-success text-dark'}">
                        <strong>#${numeroAbsoluto}</strong><br>
                        ${ficha.status == 'vendido' ? `<small>${ficha.comprador}</small>` : '<small>Disponível</small>'}
                    </div>
                </div>
            `);
        });
        new bootstrap.Modal(document.getElementById('modalNumeros')).show();
    });
}

function abrirAlterarPreco(idRifa) {
    $('#idRifaAlterar').val(idRifa);
    $('#novo_valor').val('');
    new bootstrap.Modal(document.getElementById('modalPreco')).show();
}

function handleAlterarPreco(e) {
    e.preventDefault();
    const id = $('#idRifaAlterar').val();
    let valorRaw = $('#novo_valor').val();
    let novo_valor = parseFloat(valorRaw.replace(',', '.'));
    if (!novo_valor || novo_valor < 1) {
        alert('O preço mínimo é R$ 1,00');
        return;
    }
    $.post(`/api/rifa/${id}/alterar_preco`, { valor: novo_valor }, function(response) {
        alert(response.message);
        location.reload();
    });
}

function gerarCartela(idRifa) {
    alert("Função para gerar cartela padrão da rifa " + idRifa);
}
function gerarCartelaVendedor(idRifa) {
    alert("Função para gerar cartela para vendedor da rifa " + idRifa);
}

// ========== ADMIN MODAL USUÁRIOS ==========

window.abrirAdminModal = function() {
    $('#adminModal').modal('show');
    carregarUsuarios('');
    $('#filtroUsuario').val('');
}

function carregarUsuarios(filtro) {
    $.getJSON('/api/usuarios', function(users) {
        let filtrados = users.filter(user =>
            user.nome.toLowerCase().includes(filtro.toLowerCase()) ||
            user.email.toLowerCase().includes(filtro.toLowerCase())
        );
        let tabela = `
        <table class="table table-bordered table-striped align-middle">
            <thead>
                <tr>
                    <th>Nome</th>
                    <th>Email</th>
                    <th>Tipo Atual</th>
                    <th>Novo Tipo</th>
                    <th>Ação</th>
                </tr>
            </thead>
            <tbody>
        `;
        filtrados.forEach(user => {
            tabela += `
                <tr>
                    <td>${user.nome}</td>
                    <td>${user.email}</td>
                    <td>${user.tipo}</td>
                    <td>
                        <select class="form-select form-select-sm" id="tipo-${user.id}">
                            <option value="comum" ${user.tipo === 'comum' ? 'selected' : ''}>comum</option>
                            <option value="organizador" ${user.tipo === 'organizador' ? 'selected' : ''}>organizador</option>
                            <option value="administrador" ${user.tipo === 'administrador' ? 'selected' : ''}>administrador</option>
                        </select>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="atualizarTipoUsuario(${user.id})">Atualizar</button>
                    </td>
                </tr>
            `;
        });
        tabela += '</tbody></table>';
        $('#tabelaUsuarios').html(tabela);
    });
}

window.atualizarTipoUsuario = function(userId) {
    let novoTipo = $(`#tipo-${userId}`).val();
    $.post(`/api/usuario/${userId}/alterar_tipo`, { novo_tipo: novoTipo }, function(resp) {
        if(resp.ok){
            carregarUsuarios($('#filtroUsuario').val());
        }
    });
}

// Bind para o filtro (se existir na tela)
$(document).on('input', '#filtroUsuario', function() {
    carregarUsuarios($(this).val());
});

function gerarCartela(idRifa) {
    $.post(`/api/rifa/${idRifa}/criar_cartela`, {}, function(resp) {
        if (resp.ok) {
            alert(resp.msg);
            $('#selectRifa').trigger('change'); // Atualiza a lista
        } else {
            alert(resp.msg || "Erro ao criar cartela");
        }
    });
}

function gerarCartelaVendedor(idRifa) {
    // Exemplo: abre um prompt para pegar o ID do usuário (você pode substituir por um select customizado depois)
    let idUsuario = prompt("Digite o ID do usuário autorizado (vendedor):");
    if (!idUsuario) return;
    $.post(`/api/rifa/${idRifa}/criar_cartela_para`, { id_usuario: idUsuario }, function(resp) {
        if (resp.ok) {
            alert(resp.msg);
            $('#selectRifa').trigger('change'); // Atualiza a lista
        } else {
            alert(resp.msg || "Erro ao criar cartela");
        }
    });
}

let idRifaAtual = null; // para saber em qual rifa está criando cartela

function gerarCartelaVendedor(idRifa) {
    idRifaAtual = idRifa;
    // Pega usuários autorizados
    $.getJSON(`/api/rifa/${idRifa}/autorizados`, function(usuarios) {
        let select = $('#selectUsuarioVendedor');
        select.empty();
        usuarios.forEach(u => {
            select.append(`<option value="${u.id}">${u.nome} (ID: ${u.id})</option>`);
        });
        $('#modalSelecionarUsuario').modal('show');
    });
}

// Evento do botão de criar cartela para vendedor
$(document).on('click', '#btnConfirmarCriarCartelaVendedor', function() {
    let idUsuario = $('#selectUsuarioVendedor').val();
    if (!idUsuario) {
        alert('Selecione um usuário.');
        return;
    }
    $.post(`/api/rifa/${idRifaAtual}/criar_cartela_para`, { id_usuario: idUsuario }, function(resp) {
        if (resp.ok) {
            alert(resp.msg);
            $('#selectRifa').trigger('change');
            $('#modalSelecionarUsuario').modal('hide');
        } else {
            alert(resp.msg || "Erro ao criar cartela");
        }
    });
});

$(document).on('submit', '#formCriarRifa', function(e) {
    e.preventDefault();

    let valorRaw = $('#valorNumero').val().replace(/\./g, '').replace(',', '.');
    let valorNumero = parseFloat(valorRaw);
    if (valorNumero < 1) {
        alert('O preço mínimo por número é R$ 1,00');
        return;
    }

    let data = {
        titulo: $('#tituloRifa').val(),
        descricao_premio: $('#descricaoPremio').val(),
        valor_numero: valorNumero,
        data_inicio: $('#dataInicio').val(),
        data_fim: $('#dataFim').val(),
        limite_numeros: $('#limiteNumeros').val()
    };
    $.ajax({
        url: '/api/rifa/criar',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(resp) {
            if(resp.ok) {
                alert(resp.msg);
                $('#modalCriarRifa').modal('hide');
                // Atualize a lista de rifas!
                location.reload(); // ou faça um fetch dinâmico das rifas se quiser sem reload
            } else {
                alert(resp.msg || "Erro ao criar rifa");
            }
        }
    });
});

let idRifaAdicionarVendedor = null;
let usuariosDisponiveis = [];

window.abrirModalAdicionarVendedor = function(idRifa) {
    idRifaAdicionarVendedor = idRifa;
    $.getJSON(`/api/rifa/${idRifa}/possiveis_vendedores`, function(usuarios) {
        usuariosDisponiveis = usuarios;
        atualizarSelectVendedores('');
        $('#inputBuscaVendedor').val('');
        $('#modalAdicionarVendedor').modal('show');
    });
}

function atualizarSelectVendedores(filtro) {
    let select = $('#selectUsuarioNovoVendedor');
    select.empty();
    let filtrados = usuariosDisponiveis.filter(u =>
        u.nome.toLowerCase().includes(filtro.toLowerCase()) ||
        (u.email && u.email.toLowerCase().includes(filtro.toLowerCase()))
    );
    if (filtrados.length === 0) {
        select.append('<option value="">Nenhum usuário disponível</option>');
    } else {
        filtrados.forEach(u => {
            select.append(`<option value="${u.id}">${u.nome} (ID: ${u.id})</option>`);
        });
    }
}

$(document).on('input', '#inputBuscaVendedor', function() {
    atualizarSelectVendedores($(this).val());
});

$(document).on('click', '#btnConfirmarAdicionarVendedor', function() {
    let idUsuario = $('#selectUsuarioNovoVendedor').val();
    if (!idUsuario) {
        alert('Selecione um usuário.');
        return;
    }
    $.post(`/api/rifa/${idRifaAdicionarVendedor}/adicionar_vendedor`, { id_usuario: idUsuario }, function(resp) {
        if (resp.ok) {
            alert(resp.msg);
            $('#modalAdicionarVendedor').modal('hide');
            // Você pode atualizar a lista de vendedores/cartelas, se quiser
        } else {
            alert(resp.msg || "Erro ao adicionar vendedor");
        }
    });
});

$(document).on('input', '#valorNumero', function () {
    let v = $(this).val().replace(/\D/g, '');
    v = (v/100).toFixed(2) + '';
    v = v.replace('.', ',');
    v = v.replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
    $(this).val(v);
});

function formatTelefone(v) {
    v = v.replace(/\D/g, '').slice(0, 11);
    if (v.length === 0) return '';
    if (v.length < 3) {
        return '(' + v;
    }
    if (v.length < 8) {
        return '(' + v.slice(0, 2) + ') ' + v.slice(2);
    }
    return '(' + v.slice(0, 2) + ') ' + v.slice(2, 7) + '-' + v.slice(7, 11);
}

// Mostrar toast de feedback
window.showCartMessage = function(msg) {
    $('#cartToastBody').text(msg);
    const el = document.getElementById('cartToast');
    let toast = bootstrap.Toast.getInstance(el);
    if (!toast) {
        toast = new bootstrap.Toast(el, { delay: 2000 });
    } else {
        toast._config.delay = 2000;
    }
    toast.show();
}

// Atualizar contador do carrinho na navbar
window.updateCartCount = function() {
    $.getJSON('/api/carrinho/contagem', function(data) {
        $('#cartLink').text('Carrinho (' + data.count + ')');
    });
}

window.alterarImagemFundoRifa = function(idRifa) {
    const input = $('#inputBgRifa');
    input.off('change').on('change', function(){
        const file = this.files[0];
        if(!file) return;
        const formData = new FormData();
        formData.append('imagem', file);
        $.ajax({
            url: `/api/rifa/${idRifa}/imagem_fundo`,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(){ alert('Imagem atualizada!'); },
            error: function(){ alert('Erro ao enviar imagem'); }
        });
    });
    input.trigger('click');
}

window.sortearRifa = function(idRifa){
    if(!confirm('Realizar sorteio desta rifa?')) return;
    $.post(`/api/rifa/${idRifa}/sortear`, {}, function(resp){
        if(resp.ok){
            alert('Ganhador: ' + resp.ganhador_nome + ' (#'+resp.numero+')');
            $('#selectRifa').trigger('change');
        } else {
            alert(resp.msg || 'Erro ao sortear');
        }
    });
}

window.abrirGerenciarVendedores = function(idRifa){
    $.getJSON(`/api/rifa/${idRifa}/autorizados`, function(usuarios){
        let lista = $('#listaVendedores').html('');
        if(usuarios.length === 0){
            lista.append('<li class="list-group-item">Nenhum vendedor autorizado.</li>');
        } else {
            usuarios.forEach(u => {
                lista.append(`<li class="list-group-item d-flex justify-content-between align-items-center">${u.nome} (ID: ${u.id}) <button class="btn btn-sm btn-danger" onclick="removerVendedor(${idRifa}, ${u.id})">Remover</button></li>`);
            });
        }
        $('#modalGerenciarVendedores').modal('show');
    });
}

window.removerVendedor = function(idRifa, idUsuario){
    if(!confirm('Remover este vendedor?')) return;
    $.post(`/api/rifa/${idRifa}/remover_vendedor`, { id_usuario: idUsuario }, function(resp){
        if(resp.ok){
            abrirGerenciarVendedores(idRifa);
        } else {
            alert(resp.msg || 'Erro ao remover vendedor');
        }
    });
}
