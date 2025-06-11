function formatDate(str) {
    if (!str) return '';
    const d = new Date(str);
    if (isNaN(d)) return str;
    const dia = ('0' + d.getDate()).slice(-2);
    const mes = ('0' + (d.getMonth() + 1)).slice(-2);
    const ano = d.getFullYear();
    return `${dia}/${mes}/${ano}`;
}
$(document).ready(function(){

    // Função para máscara de moeda em qualquer campo
    function mascaraMoeda(selector) {
        $(document).on('input', selector, function () {
            let v = $(this).val().replace(/\D/g, '');
            v = (v / 100).toFixed(2) + '';
            v = v.replace('.', ',');
            v = v.replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
            $(this).val(v);
        });
    }
    mascaraMoeda('#valorIngresso');
    mascaraMoeda('#novo_valor_festa');

    // Submit do formulário de criar festa
    $(document).on('submit', '#formCriarFesta', function(e){
        e.preventDefault();

        // Pega todas as datas da festa
        let datas = [];
        $('.data-festa').each(function() {
            if ($(this).val()) datas.push($(this).val());
        });

        // Pega valor como número (float, com "." decimal)
        let valorRaw = $('#valorIngresso').val().replace(/\./g, '').replace(',', '.');
        let valorIngresso = parseFloat(valorRaw);
        if (valorIngresso < 1) {
            alert('O valor mínimo do ingresso é R$ 1,00');
            return;
        }

        let data = {
            nome: $('#nomeFesta').val(),
            local: $('#localFesta').val(),
            valor_ingresso: valorIngresso,
            descricao: $('#descricaoFesta').val(),
            datas: datas
        };

        // Validação mínima
        if (!data.nome || !data.local || !data.valor_ingresso || !data.datas.length) {
            alert("Preencha todos os campos obrigatórios.");
            return;
        }

        $.ajax({
            url: '/api/festa/criar',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(resp) {
                if(resp.ok) {
                    alert(resp.msg);
                    $('#modalCriarFesta').modal('hide');
                    location.reload(); // ou atualize a lista
                } else {
                    alert(resp.msg || "Erro ao criar festa");
                }
            },
            error: function(xhr, status, err) {
                alert("Erro ao criar festa! " + (xhr.responseJSON && xhr.responseJSON.msg ? xhr.responseJSON.msg : ""));
            }
        });
    });

    // Adicionar nova data na lista de datas da festa
    $(document).on('click', '#btnAdicionarDataFesta', function () {
        $('#datasFesta').append('<input type="date" class="form-control mb-2 data-festa" required>');
    });

    // Quando seleciona uma festa na lista
    $(document).on('change', '#selectFesta', function() {
        const idFesta = $(this).val();
        $('#painelIngressos').hide();
        $('#infoFestaSelecionada').empty();

        if (!idFesta) return;

        $.getJSON(`/api/festa/${idFesta}`, function(festa) {
            exibirInfoFesta(festa); // Função central para atualizar painel
            $('#painelIngressos').show();
        });
    });

    // Abre o modal e preenche com valor atual ao clicar em "Alterar Preço"
    $(document).on('click', '#btnAlterarPrecoFesta', function() {
        console.log('Clicou em Alterar Preço Festa. data-id:', $(this).data('id'));
        $('#idFestaAlterarPreco').val($(this).data('id'));
        let precoAtual = Number($(this).data('preco')).toLocaleString('pt-BR', {minimumFractionDigits: 2});
        $('#novo_valor_festa').val(precoAtual);
        $('#modalPrecoFesta').modal('show');
    });

    // -------- FUNÇÃO CENTRAL PARA EXIBIR INFOS DA FESTA --------
    function exibirInfoFesta(festa) {
        let datasHtml = '';
        if (festa.datas && festa.datas.length) {
            datasHtml = festa.datas.map(d =>
                `<li>${formatDate(d.data ? d.data : d)}</li>`
            ).join('');
            datasHtml = `<ul class="mb-2">${datasHtml}</ul>`;
        }
        let valor = 'R$ ' + Number(festa.valor_ingresso).toLocaleString('pt-BR', {minimumFractionDigits: 2});

        $('#infoFestaSelecionada').html(`
            <div class="card mb-3">
                <div class="card-body d-flex justify-content-between">
                    <div>
                        <h4 class="mb-2">${festa.nome}</h4>
                        <p class="mb-1"><b>Local:</b> ${festa.local}</p>
                        <p class="mb-1"><b>Descrição:</b> ${festa.descricao || '-'}</p>
                        <b>Datas:</b> ${datasHtml}
                        <p class="mb-1"><b>Valor do Ingresso:</b> ${valor}</p>
                        <p class="mb-1 text-success"><b>Total de ingressos vendidos:</b> ${festa.total_vendidos}</p>
                        <p class="mb-1 text-success"><b>Valor arrecadado:</b> R$ ${Number(festa.valor_total).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</p>
                    </div>
                    <div class="text-end">
                        <button class="btn btn-outline-warning btn-sm"
                            id="btnAlterarPrecoFesta"
                            data-id="${festa.id}"
                            data-preco="${festa.valor_ingresso}">
                            Alterar Preço
                        </button>
                        <button class="btn btn-outline-dark btn-sm" onclick="alterarImagemFundoFesta(${festa.id})">Alterar Fundo</button>
                    </div>
                </div>
            </div>
        `);
    }
});

// Abre o modal para alterar preço
window.abrirAlterarPrecoFesta = function(idFesta, precoAtual) {
    $('#idFestaAlterarPreco').val(idFesta);
    $('#novo_valor_festa').val(precoAtual.toLocaleString('pt-BR', {minimumFractionDigits: 2}));
    $('#modalPrecoFesta').modal('show');
}

// Submissão do modal de alteração de preço
$(document).on('submit', '#formAlterarPrecoFesta', function(e){
    e.preventDefault();
    let id = $('#idFestaAlterarPreco').val();
    let valorRaw = $('#novo_valor_festa').val().replace(/\./g, '').replace(',', '.');
    let novo_valor = parseFloat(valorRaw);

        if (!novo_valor || novo_valor < 1) {
            alert("O valor mínimo é R$ 1,00");
            return;
        }

    $.ajax({
        url: `/api/festa/${id}/alterar_preco`,
        type: 'POST',
        data: { novo_valor: novo_valor },
        success: function(resp) {
            alert(resp.message || resp.msg);
            $('#modalPrecoFesta').modal('hide');
            $('#selectFesta').trigger('change'); // Atualiza infos
        },
        error: function(xhr){
            alert("Erro ao alterar preço!");
        }
    });
});

window.alterarImagemFundoFesta = function(idFesta) {
    const input = $('#inputBgFesta');
    input.off('change').on('change', function(){
        const file = this.files[0];
        if(!file) return;
        const formData = new FormData();
        formData.append('imagem', file);
        $.ajax({
            url: `/api/festa/${idFesta}/imagem_fundo`,
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
