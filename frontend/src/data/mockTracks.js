// Файлы лежат в папке public/:
//   public/audio/...   → в коде пишем "/audio/имя-файла.mp3"
//   public/covers/...  → в коде пишем "/covers/имя-файла.jpg"
// Имена файлов лучше писать латиницей, без пробелов.

export const mockTracks = [
   {
     id: 1,                          // уникальный номер,
     title: "Vogue",
     artist: "Madonna",
     duration: "5:16",               // как показывать в списке
     cover: "/covers/Vogue.png",   // можно оставить "" — будет градиент
     audioUrl: "/audio/Vogue.mp3",
   },
   {
     id: 2,                          // уникальный номер
     title: "505",
     artist: "Arctic Monkeys",
     duration: "4:12",               // как показывать в списке
     cover: "/covers/505.png",   // можно оставить "" — будет градиент
     audioUrl: "/audio/505.mp3",
   },
];

// Плейлисты ссылаются на треки по их id
export const mockPlaylists = [
   { id: 1, name: "Мой плейлист", cover: "", trackIds: [1, 2] },
];
