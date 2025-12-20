const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const FormData = require('form-data');
const express = require('express');

// --- Environment Variables (রেন্ডার থেকে আসবে) ---
const BOT_TOKEN = process.env.BOT_TOKEN;
const APP_URL = process.env.APP_URL; 
const CHANNEL_ID = process.env.CHANNEL_ID; // উদাহরণ: -100123456789
const CHANNEL_LINK = process.env.CHANNEL_LINK; // উদাহরণ: https://t.me/YourChannel
const PORT = process.env.PORT || 3000;

const bot = new Telegraf(BOT_TOKEN);
const app = express();

// ১. রেন্ডার সার্ভার ও সেলফ-পিং (বট যেন ঘুমিয়ে না যায়)
app.get('/', (req, res) => res.send('Bot is Running...'));
app.listen(PORT, () => {
    console.log(`Server is live on port ${PORT}`);
    
    // প্রতি ১০ মিনিট পরপর নিজেকে নিজে পিং করবে
    setInterval(() => {
        if (APP_URL) {
            axios.get(APP_URL).catch(() => {});
        }
    }, 600000); 
});

// ২. মেম্বারশিপ চেক করার ফাংশন (সাংখ্যিক আইডি সাপোর্ট করবে)
async function checkMembership(ctx) {
    try {
        const member = await ctx.telegram.getChatMember(CHANNEL_ID, ctx.from.id);
        const status = member.status;
        // মেম্বার, এডমিন বা ক্রিয়েটর হলেই ট্রু রিটার্ন করবে
        return (status === 'member' || status === 'administrator' || status === 'creator');
    } catch (e) {
        console.error("Membership check error:", e.message);
        return false;
    }
}

// ৩. /start কমান্ড
bot.start(async (ctx) => {
    const user = ctx.from;
    const welcomeText = `👋 হ্যালো **${user.first_name}**!
    
🖼 ছবি পাঠিয়ে সরাসরি লিঙ্ক পেতে হলে অবশ্যই আমাদের চ্যানেলে জয়েন থাকতে হবে। আপনার জয়েন করা না থাকলে আমি লিঙ্ক দিবো না।`;

    ctx.replyWithMarkdown(welcomeText, Markup.inlineKeyboard([
        [Markup.button.url('📢 আমাদের চ্যানেলে জয়েন করুন', CHANNEL_LINK)]
    ]));
});

// ৪. ফটো এবং ডকুমেন্ট (ছবি) প্রসেসিং
bot.on(['photo', 'document'], async (ctx) => {
    try {
        // প্রতিবার মেম্বারশিপ চেক করা হবে
        const isMember = await checkMembership(ctx);
        if (!isMember) {
            return ctx.reply(`⚠️ আপনি আমাদের চ্যানেলে নেই! \n\nলিঙ্ক পেতে হলে আপনাকে আবার জয়েন করতে হবে।`, 
                Markup.inlineKeyboard([
                    [Markup.button.url('📢 জয়েন করুন', CHANNEL_LINK)]
                ])
            );
        }

        let fileId;
        if (ctx.message.photo) {
            fileId = ctx.message.photo[ctx.message.photo.length - 1].file_id;
        } else if (ctx.message.document && ctx.message.document.mime_type.startsWith('image/')) {
            fileId = ctx.message.document.file_id;
        } else {
            return; // ছবি না হলে কিছু করবে না
        }

        // টেলিগ্রাম থেকে ফাইল লিঙ্ক পাওয়া
        const telegramFile = await ctx.telegram.getFileLink(fileId);
        
        // Catbox API তে আপলোড
        const form = new FormData();
        form.append('reqtype', 'urlupload');
        form.append('url', telegramFile.href);

        const response = await axios.post('https://catbox.moe/user/api.php', form, {
            headers: form.getHeaders()
        });

        // শুধুমাত্র ডিরেক্ট লিঙ্কটি রিপ্লাই দিবে (আপনার চাহিদা মতো)
        ctx.reply(response.data);

    } catch (error) {
        console.error("Error:", error.message);
        ctx.reply('❌ দুঃখিত, একটি সমস্যা হয়েছে। আবার চেষ্টা করুন।');
    }
});

bot.launch();

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
