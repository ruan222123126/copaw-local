const {
  Content: M0n
} = Xu, Q0n = {
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/skills": "skills",
  "/workspace": "workspace",
  "/agents": "agents",
  "/models": "models",
  "/environments": "environments"
};

function D0n() {
  const e = jp(),
    t = Kj(),
    n = e.pathname,
    r = Q0n[n] || "chat";
  return h.useEffect(() => {
    n === "/" && t("/chat", {
      replace: !0
    })
  }, [n, t]), N.jsxs(Xu, {
    children: [N.jsx($Dt, {
      selectedKey: r
    }), N.jsxs(Xu, {
      children: [N.jsx(SLt, {
        selectedKey: r
      }), N.jsxs(M0n, {
        className: "page-container",
        children: [N.jsx(ALt, {}), N.jsx("div", {
          className: "page-content",
          children: N.jsxs(mMt, {
            children: [N.jsx(hu, {
              path: "/chat",
              element: N.jsx(zve, {})
            }), N.jsx(hu, {
              path: "/channels",
              element: N.jsx(umn, {})
            }), N.jsx(hu, {
              path: "/sessions",
              element: N.jsx(xmn, {})
            }), N.jsx(hu, {
              path: "/cron-jobs",
              element: N.jsx(Qmn, {})
            }), N.jsx(hu, {
              path: "/skills",
              element: N.jsx(_gn, {})
            }), N.jsx(hu, {
              path: "/workspace",
              element: N.jsx(fOn, {})
            }), N.jsx(hu, {
              path: "/models",
              element: N.jsx(ZOn, {})
            }), N.jsx(hu, {
              path: "/environments",
              element: N.jsx(I0n, {})
            }), N.jsx(hu, {
              path: "/",
              element: N.jsx(zve, {})
            })]
          })
        })]
      })]
    })]
  })
}


// global style starts at: const L0n = Ba(templates)
