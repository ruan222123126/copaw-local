const Ahn = new khn,
  Nhn = () => "/agent/process",
  Ihn = () => "",
  Mhn = {
    theme: {
      colorPrimary: "#615CED",
      darkMode: !1,
      prefix: "CoPaw",
      leftHeader: {
        logo: "",
        title: "Work with CoPaw"
      }
    },
    sender: {
      attachments: !1,
      maxLength: 1e4,
      disclaimer: "Works for you, grows with you"
    },
    welcome: {
      greeting: "Hello, how can I help you today?",
      description: "I am a helpful assistant that can help you with your questions.",
      avatar: "/copaw-symbol.svg",
      prompts: [{
        value: "让我们开启一段新的旅程吧！"
      }, {
        value: "能告诉我你有哪些技能吗？"
      }]
    },
    api: {
      baseURL: Nhn(),
      token: Ihn()
    }
  },
  

// style block starts at: Qhn = nst(...)
