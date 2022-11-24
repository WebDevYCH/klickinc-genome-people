module.exports = function (api) {
  api.cache(true);

  const presets = [
    ["@babel/preset-env", {
      "useBuiltIns": "usage",
      "corejs": "3.6", // comment this line if ie 11 support required and uncomment code below
      // "corejs": { "version":3 }, // additional options can be used for making compatible js code with old browsers like ie 11
      // "targets": {
      //   "edge": "17",
      //   "firefox": "60",
      //   "chrome": "67",
      //   "safari": "11.1",
      //   "ie": "11"
      // }
    }]
  ];

  const plugins = [
    ["@babel/plugin-syntax-dynamic-import"]
  ]

  return {
    presets,
    plugins
  };
}
