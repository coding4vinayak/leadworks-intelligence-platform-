"""Generate embeddable JavaScript tracking snippet for customer websites."""


def generate_tracking_snippet(team_id: str, api_url: str = "https://api.leadworks.io") -> str:
    """
    Generate a JS tracking snippet that customers embed on their website.

    Tracks:
    - Page views with time-on-page
    - Scroll depth
    - Click events on CTAs
    - Form submissions (auto-captures email for identification)
    - UTM parameters
    - Referrer
    - Device/browser info

    Args:
        team_id: Customer's team ID for data routing
        api_url: Backend API URL

    Returns:
        JavaScript snippet as a string
    """
    return f'''<!-- Leadworks Tracking Snippet -->
<script>
(function(w, d, t) {{
  "use strict";

  var LW = w.Leadworks = w.Leadworks || {{}};
  LW.teamId = "{team_id}";
  LW.apiUrl = "{api_url}";
  LW.queue = LW.queue || [];
  LW.sessionStart = Date.now();

  // Generate visitor ID (persisted in localStorage)
  LW.getVisitorId = function() {{
    var vid = localStorage.getItem("lw_vid");
    if (!vid) {{
      vid = "v_" + Math.random().toString(36).substr(2, 16) + Date.now().toString(36);
      localStorage.setItem("lw_vid", vid);
    }}
    return vid;
  }};

  // Get session ID (persisted in sessionStorage)
  LW.getSessionId = function() {{
    var sid = sessionStorage.getItem("lw_sid");
    if (!sid) {{
      sid = "s_" + Math.random().toString(36).substr(2, 12);
      sessionStorage.setItem("lw_sid", sid);
    }}
    return sid;
  }};

  // Parse UTM params
  LW.getUtmParams = function() {{
    var params = new URLSearchParams(window.location.search);
    return {{
      utm_source: params.get("utm_source"),
      utm_medium: params.get("utm_medium"),
      utm_campaign: params.get("utm_campaign"),
      utm_term: params.get("utm_term"),
      utm_content: params.get("utm_content")
    }};
  }};

  // Send event to API
  LW.send = function(eventType, props) {{
    var payload = {{
      team_id: LW.teamId,
      visitor_id: LW.getVisitorId(),
      session_id: LW.getSessionId(),
      event_type: eventType,
      url: window.location.href,
      page_title: document.title,
      referrer: document.referrer,
      timestamp: new Date().toISOString(),
      properties: props || {{}},
      utm: LW.getUtmParams(),
      screen: {{ width: screen.width, height: screen.height }},
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
    }};

    // Use sendBeacon for reliability (fires even on page unload)
    if (navigator.sendBeacon) {{
      navigator.sendBeacon(
        LW.apiUrl + "/api/v1/track/event",
        JSON.stringify(payload)
      );
    }} else {{
      var xhr = new XMLHttpRequest();
      xhr.open("POST", LW.apiUrl + "/api/v1/track/event", true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.send(JSON.stringify(payload));
    }}
  }};

  // Identify visitor (link to lead)
  LW.identify = function(email, properties) {{
    LW.send("identify", {{ email: email, ...properties }});
    localStorage.setItem("lw_email", email);
  }};

  // Track custom event
  LW.track = function(eventName, properties) {{
    LW.send(eventName, properties || {{}});
  }};

  // Auto-track page view
  LW.send("page_view", {{}});

  // Track time on page
  var pageStartTime = Date.now();
  window.addEventListener("beforeunload", function() {{
    var timeOnPage = Math.round((Date.now() - pageStartTime) / 1000);
    LW.send("page_exit", {{ time_on_page_seconds: timeOnPage }});
  }});

  // Track scroll depth
  var maxScroll = 0;
  var scrollThresholds = [25, 50, 75, 90];
  var firedThresholds = {{}};
  window.addEventListener("scroll", function() {{
    var scrollPercent = Math.round(
      (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
    );
    if (scrollPercent > maxScroll) {{
      maxScroll = scrollPercent;
      scrollThresholds.forEach(function(threshold) {{
        if (scrollPercent >= threshold && !firedThresholds[threshold]) {{
          firedThresholds[threshold] = true;
          LW.send("scroll_depth", {{ depth: threshold }});
        }}
      }});
    }}
  }});

  // Auto-capture form submissions
  document.addEventListener("submit", function(e) {{
    var form = e.target;
    var formData = {{}};
    var emailField = null;

    // Extract form data
    var inputs = form.querySelectorAll("input, select, textarea");
    inputs.forEach(function(input) {{
      var name = input.name || input.id || "";
      var value = input.value || "";
      if (input.type !== "password" && input.type !== "hidden") {{
        formData[name] = value;
      }}
      // Auto-detect email field
      if (input.type === "email" || name.toLowerCase().includes("email")) {{
        emailField = value;
      }}
    }});

    LW.send("form_submit", {{
      form_id: form.id || form.action,
      form_data: formData
    }});

    // Auto-identify if email found
    if (emailField) {{
      LW.identify(emailField, formData);
    }}
  }});

  // Track outbound link clicks
  document.addEventListener("click", function(e) {{
    var link = e.target.closest("a");
    if (link && link.hostname !== window.location.hostname) {{
      LW.send("outbound_click", {{
        url: link.href,
        text: link.innerText.substring(0, 100)
      }});
    }}

    // Track CTA button clicks
    if (e.target.closest("[data-lw-track]")) {{
      var el = e.target.closest("[data-lw-track]");
      LW.send("cta_click", {{
        track_id: el.getAttribute("data-lw-track"),
        text: el.innerText.substring(0, 100)
      }});
    }}
  }});

  // SPA support: track route changes
  var lastUrl = window.location.href;
  new MutationObserver(function() {{
    if (window.location.href !== lastUrl) {{
      lastUrl = window.location.href;
      pageStartTime = Date.now();
      LW.send("page_view", {{}});
    }}
  }}).observe(document.body, {{ childList: true, subtree: true }});

  console.log("[Leadworks] Tracking initialized");
}})(window, document);
</script>'''


def generate_tracking_routes_code() -> str:
    """Returns info about the tracking API endpoints needed."""
    return """
    Tracking API Endpoints:
    - POST /api/v1/track/event - Receive tracking events from JS snippet
    - POST /api/v1/track/identify - Link visitor to lead
    - GET /api/v1/track/visitors/active - Get active visitors (real-time)
    - GET /api/v1/track/visitor/{visitor_id}/history - Get visitor browsing history
    - GET /api/v1/track/lead/{lead_id}/activity - Get lead's tracking data
    - GET /api/v1/track/snippet - Get JS snippet for embedding
    """
