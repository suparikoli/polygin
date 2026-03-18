# 📘 Polygin WhatsApp API Documentation

## 🔐 Authentication

All API requests require authentication using an API key.

### Method 1: Bearer Token (Template API)

```
Authorization: Bearer API_KEY
```

### Method 2: Query Parameter (Conversational API)

```
?token=API_KEYS
```

---

# 🚀 1. Template Messaging API

Used for sending **pre-approved WhatsApp templates** (campaigns, notifications, etc.).

## 📌 Endpoint

```
POST https://polyg.in/api/v1/send_templet
```

## 📌 Headers

```
Content-Type: application/json
Authorization: Bearer API_KEY
```

## 📌 Request Body

```json
{
  "sendTo": "+1234567890",
  "templetName": "YourTemplateName",
  "exampleArr": ["example_key_1", "example_key_2"],
  "token": "YourAPIToken",
  "mediaUri": "OptionalMediaUri"
}
```

## 📌 Parameters

| Parameter   | Type   | Required | Description                                |
| ----------- | ------ | -------- | ------------------------------------------ |
| sendTo      | string | ✅        | Recipient phone number (with country code) |
| templetName | string | ✅        | Approved WhatsApp template name            |
| exampleArr  | array  | ✅        | Variables to populate template             |
| token       | string | ✅        | API token                                  |
| mediaUri    | string | ❌        | Media URL (if template supports media)     |

## ✅ Success Response

```json
{
  "success": true,
  "metaResponse": {
    "message_id": "message_id_here",
    "status": "sent"
  }
}
```

---

# 💬 2. Conversational Messaging API

Used for sending **real-time messages**, including text, media, and interactive messages.

## 📌 Endpoint

```
POST https://polyg.in/api/v1/send-message?token=API_KEYS
```

## 📌 Request Body Format

```json
{
  "messageObject": { ... }
}
```

## ✅ Success Response

```json
{
  "success": true,
  "message": "Message sent successfully!"
}
```

## ❌ Failure Response

```json
{
  "success": false,
  "message": "<REASON>"
}
```

---

# 📩 Message Types

---

## 2.1 📝 Text Message

```json
{
  "to": "18876656789",
  "type": "text",
  "text": {
    "preview_url": false,
    "body": "text-message-content"
  }
}
```

### Notes:

* `preview_url`: Enable/disable link preview

---

## 2.2 🖼️ Image Message

```json
{
  "to": "18876656789",
  "type": "image",
  "image": {
    "link": "https://image-url"
  }
}
```

### Supported Formats:

* jpg, jpeg, png, webp

### Max Size:

* 5 MB

---

## 2.3 🎧 Audio Message

```json
{
  "to": "18876656789",
  "type": "audio",
  "audio": {
    "link": "https://audio-url"
  }
}
```

### Supported Formats:

* mp3, aac, m4a, amr, opus

### Max Size:

* 16 MB

---

## 2.4 📄 Document Message

```json
{
  "to": "18876656789",
  "type": "document",
  "document": {
    "link": "https://document-url",
    "caption": "Document caption"
  }
}
```

### Supported Formats:

* pdf, doc, docx, xls, xlsx, ppt, pptx, txt

### Max Size:

* 75 MB

---

## 2.5 🎥 Video Message

```json
{
  "to": "18876656789",
  "type": "video",
  "video": {
    "link": "https://video-url",
    "caption": "Video caption"
  }
}
```

### Supported Formats:

* mp4, m4v, 3gp

### Max Size:

* 16 MB

---

# 🔘 3. Interactive Messages

---

## 3.1 📋 List Message

```json
{
  "to": "18876656789",
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {
      "type": "text",
      "text": "Header text"
    },
    "body": {
      "text": "Body text"
    },
    "footer": {
      "text": "Footer text"
    },
    "action": {
      "button": "Choose option",
      "sections": [
        {
          "title": "Section 1",
          "rows": [
            {
              "id": "option1",
              "title": "Option 1",
              "description": "Description 1"
            }
          ]
        }
      ]
    }
  }
}
```

---

## 3.2 🔘 Reply Buttons

```json
{
  "to": "18876656789",
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {
      "text": "Choose an option"
    },
    "action": {
      "buttons": [
        {
          "type": "reply",
          "reply": {
            "id": "btn1",
            "title": "Yes"
          }
        },
        {
          "type": "reply",
          "reply": {
            "id": "btn2",
            "title": "No"
          }
        }
      ]
    }
  }
}
```

---

# ⚙️ Best Practices

### ✅ Use Template API when:

* Sending campaigns
* Notifications outside 24-hour window
* Pre-approved messages

### ✅ Use Conversational API when:

* Replying to users
* Sending real-time updates
* Handling chat flows

---

# ⚠️ Common Mistakes

* ❌ Wrong phone format → Always include country code
* ❌ Template not approved → Message will fail
* ❌ Media too large → Check size limits
* ❌ Missing token → Authentication error

---

# 🧩 Example Use Cases

### 📢 Campaign Blast

→ Use Template API

### 🤖 Chatbot Flow

→ Use Conversational API + interactive messages

### 📎 Sending Documents (e.g. invoices)

→ Use Document message

### 📊 Lead Qualification Flow

→ Use List + Reply Buttons

---

# 🔚 Summary

| Feature           | API Used           |
| ----------------- | ------------------ |
| Campaign messages | Template API       |
| Real-time chat    | Conversational API |
| Media sharing     | Conversational API |
| Buttons & lists   | Conversational API |

---

If you want, I can next:

* Build a **Node.js / Python wrapper for this**
* Show **how to plug this into your Frappe/ERPNext**
* Or design a **full WhatsApp sales funnel for Polemarch** 🚀
