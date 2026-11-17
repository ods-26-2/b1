# Publicar uma versão

Uma tag `vX.Y.Z` publica `ods-validator` no PyPI e no npm e cria uma release no
GitHub com o `.whl`, o `.tar.gz` e o `.tgz` anexados. O C++ não tem registro:
quem consome usa a própria tag (`FetchContent`). Os três pacotes têm sempre o
mesmo número de versão, que é a versão do contrato.

## Configuração (uma vez)

**PyPI** (publicação sem token, "trusted publishing"):

1. Crie uma conta em pypi.org e ative a autenticação em dois fatores.
2. Em <https://pypi.org/manage/account/publishing/>, em *Create a new pending
   publisher*, preencha: projeto `ods-validator`, dono `ods-26-2`, repositório
   `b1`, workflow `release.yml`, ambiente `pypi`.

**npm** (o pacote precisa existir antes de configurar a publicação sem token):

1. Crie uma conta em npmjs.com e ative a autenticação em dois fatores.
2. Publique a primeira versão da sua máquina:
   ```bash
   cd jsonValidatorTs
   npm install
   npm login
   npm publish --access public
   ```
3. Em npmjs.com, no pacote, *Settings → Trusted publisher → GitHub Actions*:
   organização `ods-26-2`, repositório `b1`, workflow `release.yml`, ambiente
   `npm`.

**GitHub:** os ambientes `pypi` e `npm` são criados no primeiro uso. Em
*Settings → Environments* dá para exigir aprovação manual antes de publicar,
o que serve de freio contra uma tag errada.

## A cada versão

1. Atualize o número nos três lugares (precisam ser iguais, o workflow confere):
   `jsonValidatorPy/pyproject.toml`, `jsonValidatorTs/package.json` e
   `jsonValidatorCpp/CMakeLists.txt` (`project(... VERSION X.Y.Z)`).
   Para o npm: `cd jsonValidatorTs && npm version X.Y.Z --no-git-tag-version`.
2. Se mudou algum schema: `python tools/generate_examples.py` e commite os
   `examples/`.
3. Faça o merge na `main` com o CI passando.
4. Crie e envie a tag:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. Acompanhe a aba *Actions*. O workflow `release` roda os testes, confere as
   versões, publica no PyPI e no npm e cria a release.

Se a versão já estiver no npm (caso do primeiro release, publicado à mão), o
workflow detecta e pula essa etapa.

## Como os componentes instalam

```bash
pip install ods-validator==X.Y.Z            # Python
npm install ods-validator@X.Y.Z --save-exact  # TypeScript
```

C++: `URL https://github.com/ods-26-2/b1/archive/refs/tags/vX.Y.Z.tar.gz` no
`FetchContent_Declare` (veja `jsonValidatorCpp/README.md`).

## Cuidados

- Uma versão publicada no PyPI ou no npm não pode ser sobrescrita nem reaproveitada.
  Se publicar algo errado, corrija e publique a versão seguinte (no PyPI dá para
  marcar a errada como *yanked*).
- Se o `publish-npm` falhar com erro 404 ou de token expirado, confira se o
  *trusted publisher* do npm aponta para o repositório, o arquivo `release.yml` e
  o ambiente `npm`, e se o npm do runner é 11.5.1 ou mais novo (o workflow o instala).
- Se o `publish-pypi` falhar, confira se o publicador pendente ou confiável do
  PyPI usa exatamente o nome `release.yml` e o ambiente `pypi`.
- Os endereços e os campos dos formulários do PyPI e do npm podem mudar; em caso
  de dúvida, vale conferir a documentação deles.
