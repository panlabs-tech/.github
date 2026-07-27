// O padrão de mensagem de commit deste repo, lido pelo `commit-msg` de
// `lefthook.yml`. Conventional Commits com subject minúsculo, que é a convenção
// declarada em `AGENTS.md` -- e o mesmo formato que o squash-merge leva para a
// branch default, porque o título do PR vira a mensagem do commit que aterrissa.
//
// O arquivo é `.mjs` e não `.js` por um motivo mecânico: este repo não tem
// `package.json`, então o Node trata `.js` como CommonJS e `export default`
// falha. A extensão é o que declara o módulo aqui.
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // pt-BR em prosa e commits (AGENTS.md): a regra de caso do subject vale,
    // a de idioma não é verificável por lint e vive na convenção escrita.
    "subject-case": [2, "always", "lower-case"],
  },
};
