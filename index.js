const { Telegraf } = require('telegraf');
const axios = require('axios');
const FormData = require('form-data');
const express = require('express');

// Environment Variables
const BOT_TOKEN = process.env.BOT_TOKEN;
const APP_URL = process.env.APP_URL; // আপনার রেন্ডার অ্যাপের URL
const PORT = process.env.PORT || 3000;

const bot = new Telegraf(BOT_TOKEN);
const app = express();

// রেন্ডার সার্ভার সেটআপ
app.get('/', (req, res) => {
    res.send('Bot is Running and Active!');
});

app.listen(PORT, () => {
    console.log(`Server started on port ${PORT}`);
    
    // বটকে জাগিয়ে রাখার ব্যবস্থা (Self-Ping)
    setInterval(() => {
        if (APP_URL) {
            axios.get(APP_URL)
                .then(() => console.log('Self-ping successful!'))
                .catch(err => console.log('Ping failed, but bot is still running.'));
        }
    }, 600000); // ১০ মিনিট পরপর পিং করবে
});

// /start কমান্ড
bot.start((ctx) => {
    const user = ctx.from;
    const msg = `👋 হ্যালো **${user.first_name}**!
    
👤 **আপনার প্রোফাইল তথ্য:**
🆔 ইউজার আইডি: \`${user.id}\`
📜 নাম: ${user.first_name} ${user.last_name || ''}
🔗 ইউজারনেম: @${user.username || 'নেই'}

🖼 আপনি আমাকে যেকোনো ছবি পাঠান, আমি সেটির **Direct JPG Link** দিয়ে দেব।`;
    
    ctx.replyWithMarkdown(msg);
});

// ছবি থেকে ডিরেক্ট লিঙ্ক তৈরির কাজ
bot.on(['photo', 'document'], async (ctx) => {
    try {
        let fileId;

        // ফটো বা ডকুমেন্ট চেক করা
        if (ctx.message.photo) {
            fileId = ctx.message.photo[ctx.message.photo.length - 1].file_id;
        } else if (ctx.message.document && ctx.message.document.mime_type.startsWith('image/')) {
            fileId = ctx.message.document.file_id;
        } else {
            return; 
        }

        ctx.reply('⏳ ডিরেক্ট লিঙ্ক তৈরি হচ্ছে... দয়া করে অপেক্ষা করুন।');

        // ১. টেলিগ্রাম থেকে ফাইল পাথ নেওয়া
        const fileLink = await ctx.telegram.getFileLink(fileId);
        const imageUrl = fileLink.href;

        // ২. Catbox.moe তে আপলোড করা
        const form = new FormData();
        form.append('reqtype', 'urlupload');
        form.append('url', imageUrl);

        const response = await axios.post('https://catbox.moe/user/api.php', form, {
            headers: form.getHeaders()
        });

        const directLink = response.data; // এটি সরাসরি https://files.catbox.moe/xxx.jpg লিঙ্ক দেয়

        // ৩. ইউজারকে আউটপুট দেওয়া
        const finalMsg = `✅ **লিঙ্ক তৈরি সফল!**

🔗 সরাসরি লিঙ্ক: ${directLink}`;
        
        ctx.reply(finalMsg);

    } catch (error) {
        console.error(error);
        ctx.reply('❌ দুঃখিত, লিঙ্ক তৈরি করতে সমস্যা হয়েছে। আবার চেষ্টা করুন।');
    }
});

bot.launch();

// কন্ট্রোল সি বা টার্মিনেট করলে বট বন্ধ হবে
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
